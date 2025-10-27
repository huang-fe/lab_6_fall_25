#!/usr/bin/env python3
"""
Enhanced Low-Latency Whisper Node
Inspired by the pupster.py implementation with modern async architecture.
Features:
- Real-time audio streaming
- Async processing to prevent blocking
- Command queue system
- Thread-safe operations
- Reduced latency compared to old implementation
"""

import asyncio
import threading
import queue
import logging
from typing import Optional, Tuple
import time
import io
import wave

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String
import sounddevice as sd
import numpy as np

# Import centralized API configuration
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
from api_keys import get_openai_client, WHISPER_MODEL

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisper_ping")

# OpenAI client from centralized config
client = get_openai_client()

class EnhancedWhisperNode(Node):
    """Enhanced Whisper node with low-latency async processing."""
    
    def __init__(self):
        super().__init__('enhanced_whisper_node')
        
        # ROS2 Publishers
        self.transcription_publisher = self.create_publisher(
            String,
            '/transcription',  # Standard transcription topic
            10
        )
        self.user_query_publisher = self.create_publisher(
            String,
            'user_query_topic',  # Legacy compatibility
            10
        )
        
        # ROS2 Subscribers for microphone control
        self.mic_control_subscriber = self.create_subscription(
            String,
            '/microphone_control',  # Commands: 'mute', 'unmute'
            self.microphone_control_callback,
            10
        )
        
        # Subscriber for response completion signal
        self.response_complete_subscriber = self.create_subscription(
            String,
            '/response_complete',  # Signal when entire response cycle is done
            self.response_complete_callback,
            10
        )
        
        # Audio configuration
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_duration = 5.0  # Reduced from 5.0 for lower latency
        self.silence_threshold = 0.01
        
        # Thread-safe audio queue
        self.audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=5)
        self.processing_lock = asyncio.Lock()
        
        # Audio streaming setup
        self.is_recording = False
        self.audio_stream = None
        
        # Microphone control state with double-check system
        self.microphone_muted = False
        self.mute_reason = ""
        self.mute_timestamp = None
        self.processing_user_input = False
        self.fixed_mute_duration = 5.0  # Fixed 5-second mute after LLM speaks
        
        # Background processing
        self.processing_task = None
        self.running = True
        
        # Emergency unmute timer - checks for stuck mute states every 10 seconds
        self.emergency_unmute_timer = self.create_timer(10.0, self.emergency_unmute_check)
        self.max_mute_duration = 30.0  # Maximum seconds to stay muted
        
        logger.info('Enhanced Whisper Node initialized with low-latency processing and safety checks')
    
    def start_audio_streaming(self):
        """Start continuous audio streaming with callback processing."""
        try:
            import contextlib
            
            # Suppress JACK audio warnings during stream initialization
            with contextlib.redirect_stderr(None):
                self.audio_stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    callback=self.audio_callback,
                    blocksize=int(self.sample_rate * 0.1),  # 100ms blocks for low latency
                    dtype=np.float32
                )
            self.audio_stream.start()
            self.is_recording = True
            logger.info("Audio streaming started")
        except Exception as e:
            logger.error(f"Failed to start audio streaming: {e}")
    
    def microphone_control_callback(self, msg):
        """Handle microphone control commands."""
        command = msg.data.lower().strip()
        
        if command == 'mute':
            if not self.microphone_muted:
                self.microphone_muted = True
                self.mute_reason = "Manual mute"
                logger.info("🔇 Microphone MUTED (manual control)")
        elif command == 'unmute':
            if self.microphone_muted:
                self.microphone_muted = False
                self.mute_reason = ""
                logger.info("🎤 Microphone UNMUTED (manual control)")
        else:
            logger.warning(f"Unknown microphone control command: {command}")
    
    def response_complete_callback(self, msg):
        """Handle response completion signal with double-checks before unmuting."""
        if not self.microphone_muted:
            logger.debug("Received response complete signal but microphone was already unmuted")
            return
        
        if not self.processing_user_input:
            logger.warning("Received completion signal but not processing user input - ignoring")
            return
        
        # FIXED 5-second mute time after LLM speaks
        if self.mute_timestamp:
            time_muted = time.time() - self.mute_timestamp
            if time_muted < self.fixed_mute_duration:
                remaining_time = self.fixed_mute_duration - time_muted
                logger.info(f"⏱️  Response complete but enforcing 5s mute - {remaining_time:.1f}s remaining")
                # Schedule unmute after fixed duration
                import threading
                timer = threading.Timer(remaining_time, self._delayed_unmute)
                timer.start()
                return
        
        # All checks passed - safe to unmute
        self._safe_unmute("response cycle complete")
    
    def _delayed_unmute(self):
        """Delayed unmute after minimum duration."""
        if self.microphone_muted and self.processing_user_input:
            self._safe_unmute("delayed unmute after minimum duration")
    
    def _safe_unmute(self, reason: str):
        """Safely unmute microphone with full state reset."""
        self.microphone_muted = False
        self.mute_reason = ""
        self.mute_timestamp = None
        self.processing_user_input = False
        logger.info(f"🎤 Microphone SAFELY UNMUTED ({reason}) - ready for next input")
    
    def emergency_unmute_check(self):
        """Emergency check to prevent microphone from staying muted too long."""
        if not self.microphone_muted:
            return  # Not muted, nothing to check
        
        if not self.mute_timestamp:
            logger.warning("⚠️  Microphone muted but no timestamp - emergency unmuting")
            self._safe_unmute("emergency - no timestamp")
            return
        
        time_muted = time.time() - self.mute_timestamp
        if time_muted > self.max_mute_duration:
            logger.warning(f"🚨 EMERGENCY UNMUTE: Microphone muted for {time_muted:.1f}s (max: {self.max_mute_duration}s)")
            self._safe_unmute("emergency - exceeded max duration")
        elif time_muted > self.fixed_mute_duration:
            logger.info(f"⏰ Microphone muted for {time_muted:.1f}s - beyond 5s fixed duration, still waiting")
    
    def audio_callback(self, indata, frames, time, status):
        """Real-time audio callback - non-blocking."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        # Skip processing if microphone is muted
        if self.microphone_muted:
            return
        
        # Convert to int16 and check for silence
        audio_data = (indata.flatten() * 32767).astype(np.int16)
        
        # Simple voice activity detection
        if np.max(np.abs(audio_data)) > self.silence_threshold * 32767:
            try:
                # Non-blocking queue put
                if not self.audio_queue.full():
                    self.audio_queue.put_nowait(audio_data)
            except queue.Full:
                # Drop oldest audio if queue is full
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait(audio_data)
                except queue.Empty:
                    pass
    
    async def start_processing(self):
        """Start background audio processing task."""
        self.processing_task = asyncio.create_task(self._process_audio_queue())
        logger.info("Audio processing task started")
    
    async def _process_audio_queue(self):
        """Background task to process audio chunks asynchronously."""
        audio_buffer = []
        last_audio_time = time.time()
        
        while self.running:
            try:
                # Check for audio with timeout
                try:
                    audio_chunk = self.audio_queue.get_nowait()
                    audio_buffer.extend(audio_chunk)
                    last_audio_time = time.time()
                except queue.Empty:
                    # Check if we should process accumulated audio
                    if audio_buffer and (time.time() - last_audio_time) > 1.0:
                        await self._process_audio_buffer(audio_buffer)
                        audio_buffer = []
                    await asyncio.sleep(0.1)
                    continue
                
                # Process when buffer reaches target duration
                if len(audio_buffer) >= self.sample_rate * self.chunk_duration:
                    await self._process_audio_buffer(audio_buffer)
                    audio_buffer = []
                    
            except Exception as e:
                logger.error(f"Error in audio processing loop: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_audio_buffer(self, audio_buffer):
        """Process accumulated audio buffer with Whisper."""
        if not audio_buffer:
            return
        
        async with self.processing_lock:
            try:
                start_time = time.time()
                
                # Convert to numpy array and create WAV
                audio_array = np.array(audio_buffer, dtype=np.int16)
                wav_data = self._create_wav_bytes(audio_array)
                
                # Transcribe with OpenAI Whisper API (async)
                transcription = await asyncio.get_event_loop().run_in_executor(
                    None, self._transcribe_audio, wav_data
                )
                
                processing_time = time.time() - start_time
                
                if transcription and transcription.strip():
                    # Filter out single words (likely transcription errors)
                    words = transcription.strip().split()
                    if len(words) < 2:
                        logger.info(f"Filtered single word: '{transcription}' (likely transcription error)")
                        return
                    
                    logger.info(f"Transcription ({processing_time:.2f}s): {transcription}")
                    await self._publish_transcription(transcription)
                else:
                    logger.debug("No transcription result or empty result")
                    
            except Exception as e:
                logger.error(f"Error processing audio buffer: {e}")
    
    def _create_wav_bytes(self, audio_data: np.ndarray) -> bytes:
        """Create WAV bytes from audio data."""
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        return wav_io.getvalue()
    
    def _transcribe_audio(self, wav_data: bytes) -> Optional[str]:
        """Transcribe audio using OpenAI Whisper API."""
        try:
            wav_file = io.BytesIO(wav_data)
            wav_file.name = "audio.wav"  # Required for OpenAI API
            
            response = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=wav_file,
                response_format="text",
                language="en"  # Specify language for better performance
            )
            return response.strip() if response else None
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None

    async def _publish_transcription(self, transcription: str):
        """Publish transcription to ROS2 topics and immediately mute microphone with double-check."""
        msg = String()
        msg.data = transcription
        
        # Publish to both topics for compatibility
        self.transcription_publisher.publish(msg)
        self.user_query_publisher.publish(msg)
        
        # Immediately mute microphone with robust state tracking
        self.microphone_muted = True
        self.mute_reason = "Processing user input - FULL CYCLE"
        self.mute_timestamp = time.time()
        self.processing_user_input = True
        
        logger.info(f"Published transcription: {transcription}")
        logger.info("🔇 Microphone LOCKED MUTED (fixed 5-second mute after LLM speaks)")
    
    def stop_processing(self):
        """Stop audio processing and streaming."""
        self.running = False
        
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            
        if self.processing_task:
            self.processing_task.cancel()
            
        logger.info("Audio processing stopped")


async def main_async(args=None):
    """Async main function with proper ROS2 and asyncio integration."""
    rclpy.init(args=args)

    # Create the enhanced whisper node
    whisper_node = EnhancedWhisperNode()
    
    # Store the event loop reference in the node for thread-safe access
    whisper_node._loop = asyncio.get_running_loop()
    
    # Set up ROS2 executor
    executor = SingleThreadedExecutor()
    executor.add_node(whisper_node)
    
    try:
        logger.info("Starting enhanced whisper node with real-time processing...")
        logger.info("Features:")
        logger.info("  - Continuous audio streaming")
        logger.info("  - Async transcription processing")
        logger.info("  - Voice activity detection")
        logger.info("  - Low-latency pipeline")
        logger.info("Say something to test the transcription...")
        
        # Start audio streaming and processing
        whisper_node.start_audio_streaming()
        await whisper_node.start_processing()
        
        # Run ROS2 executor in asyncio-compatible way
        while rclpy.ok():
            # Spin once with timeout to allow asyncio tasks to run
            executor.spin_once(timeout_sec=0.1)
            await asyncio.sleep(0.01)  # Allow other async tasks to run

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Clean shutdown
        whisper_node.stop_processing()
        executor.shutdown()
    rclpy.shutdown()

def main(args=None):
    """Main entry point that sets up asyncio event loop."""
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")

if __name__ == '__main__':
    main()
