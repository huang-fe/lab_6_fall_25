#!/usr/bin/env python3
"""
Enhanced Karel GPT Commander
Modernized with async architecture inspired by pupster.py implementation.
Features:
- Async LLM processing to prevent blocking
- Command queue system for smooth robot control
- Modern OpenAI TTS instead of pyttsx3
- Thread-safe operations
- Improved error handling and logging
"""

import asyncio
import threading
import queue
import logging
from typing import Optional, Tuple, Dict, Any
from abc import ABC, abstractmethod
import time
import json

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String
import karel  # Importing your KarelPupper API

# Import centralized API configuration
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
from api_keys import get_openai_client, GPT_MODEL, TTS_MODEL, TTS_VOICE, MAX_TOKENS, TEMPERATURE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("karel_commander")

# OpenAI client from centralized config
client = get_openai_client()

# Command system for async robot control
class Command(ABC):
    """Base class for all robot commands"""
    
    def __init__(self, name: str):
        self.name = name
        self.timestamp = time.time()
    
    @abstractmethod
    async def execute(self, pupper: karel.KarelPupper) -> Tuple[bool, str]:
        """Execute the command and return success status and message"""
        pass

class KarelMethodCommand(Command):
    """Generic command that calls any karel.KarelPupper method by name."""
    
    def __init__(self, method_name: str, display_name: str = None, duration: float = 1.5):
        """
        Args:
            method_name: The name of the method to call on KarelPupper (e.g., 'move_forward')
            display_name: Optional human-readable name for logging (defaults to method_name)
            duration: Time in seconds to wait for the action to complete (default 1.5s)
        """
        super().__init__(display_name or method_name)
        self.method_name = method_name
        self.duration = duration
    
    async def execute(self, pupper: karel.KarelPupper) -> Tuple[bool, str]:
        try:
            # Dynamically get and call the method
            method = getattr(pupper, self.method_name)
            method()  # Direct call - all karel methods are synchronous
            
            # Wait for the physical action to complete
            await asyncio.sleep(self.duration)
            
            return True, f"{self.name} command executed successfully"
        except AttributeError:
            return False, f"Method '{self.method_name}' not found on KarelPupper"
        except Exception as e:
            return False, f"{self.name} command failed: {e}"

class GenericMoveCommand(Command):
    """Generic move command with velocity control."""
    
    def __init__(self, linear_x: float, linear_y: float, angular_z: float, duration: float = 1.5):
        """
        Args:
            linear_x: Forward/backward velocity in m/s (capped at ±1.0)
            linear_y: Left/right velocity in m/s (capped at ±0.5)
            angular_z: Rotation velocity in rad/s (capped at ±2.5)
            duration: Time in seconds to maintain this velocity (default 1.5s)
        """
        super().__init__("generic_move")
        # Clamp values to safe limits and ensure float type
        self.linear_x = float(max(-1.0, min(1.0, linear_x)))
        self.linear_y = float(max(-0.5, min(0.5, linear_y)))
        self.angular_z = float(max(-2.5, min(2.5, angular_z)))
        self.duration = duration
    
    async def execute(self, pupper: karel.KarelPupper) -> Tuple[bool, str]:
        try:
            pupper.move(self.linear_x, self.linear_y, self.angular_z)
            
            # Wait for the movement to complete
            await asyncio.sleep(self.duration)
            
            return True, f"Move command executed: x={self.linear_x:.2f}, y={self.linear_y:.2f}, z={self.angular_z:.2f}"
        except Exception as e:
            return False, f"Generic move command failed: {e}"

class SpeakCommand(Command):
    def __init__(self, message: str, node: "EnhancedGPTCommanderNode" = None):
        super().__init__("speak")
        self.message = message
        self.node = node
    
    async def execute(self, pupper: karel.KarelPupper) -> Tuple[bool, str]:
        try:
            logger.info(f"🗣️  Starting TTS: '{self.message}'")
            
            # Use OpenAI TTS for better quality speech
            await asyncio.get_event_loop().run_in_executor(None, self._speak_openai, self.message)
            
            # LONGER delay after speech to ensure audio is completely finished
            # This prevents premature unmuting during TTS playback
            await asyncio.sleep(1.0)  # Increased from 0.2s to 1.0s
            
            logger.info("✅ TTS playback completed (with safety delay)")
            return True, f"Spoke: {self.message}"
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return False, f"Speak command failed: {e}"
    
    def _speak_openai(self, text: str):
        """Use OpenAI TTS for speech synthesis."""
        try:
            import sys
            import contextlib
            import pyaudio
            import numpy as np
            
            # Create TTS audio
            response = client.audio.speech.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=text,
                response_format="pcm"
            )
            
            # Play audio - suppress JACK audio warnings during PyAudio init
            with contextlib.redirect_stderr(None):
                p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)
            
            for chunk in response.iter_bytes(chunk_size=1024):
                stream.write(chunk)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            # Fallback to simple print
            print(f"Robot says: {text}")

class CompletionSignalCommand(Command):
    def __init__(self, node: "EnhancedGPTCommanderNode"):
        super().__init__("completion_signal")
        self.node = node
    
    async def execute(self, pupper: karel.KarelPupper) -> Tuple[bool, str]:
        """Signal that the entire response cycle is complete."""
        try:
            logger.info("🏁 All commands completed - signaling response cycle complete")
            self.node.signal_response_complete()
            logger.info("📡 Completion signal sent - microphone should unmute now")
            return True, "Response completion signaled"
        except Exception as e:
            logger.error(f"Failed to signal completion: {e}")
            return False, f"Failed to signal completion: {e}"

class EnhancedGPTCommanderNode(Node):
    """Enhanced GPT Commander with async processing and command queuing."""
    
    def __init__(self):
        super().__init__('enhanced_gpt_commander_node')

        # ROS2 subscriptions and publishers
        self.subscription = self.create_subscription(
            String,
            'user_query_topic',
            self.query_callback,
            10
        )
        
        # Also listen to the standard transcription topic
        self.transcription_subscription = self.create_subscription(
            String,
            '/transcription',
            self.query_callback,
            10
        )

        self.response_publisher = self.create_publisher(
            String,
            'gpt4_response_topic',
            10
        )
        
        # Microphone control publisher (to prevent feedback)
        self.mic_control_publisher = self.create_publisher(
            String,
            '/microphone_control',
            10
        )
        
        # Response completion publisher (signals when entire response cycle is done)
        self.response_complete_publisher = self.create_publisher(
            String,
            '/response_complete',
            10
        )

        # Initialize KarelPupper robot control
        self.pupper = karel.KarelPupper()
        
        # Command queue system
        self.command_queue = asyncio.Queue()
        self.queue_running = False
        self.queue_task = None
        self.current_command_task = None
        
        # Processing lock to prevent concurrent LLM calls
        self.processing_lock = asyncio.Lock()
        
        # Latest message tracking - only process the most recent
        self.latest_message = None
        self.latest_message_timestamp = None
        self.current_processing_task = None
        
        # Conversation history for better context
        self.conversation_history = []
        
        # Start command processor
        self.start_command_processor()
        
        logger.info('Enhanced GPT Commander Node initialized with async processing')
    
    def mute_microphone(self):
        """Mute the microphone to prevent feedback."""
        msg = String()
        msg.data = 'mute'
        self.mic_control_publisher.publish(msg)
        logger.debug("Sent microphone mute command")
    
    def unmute_microphone(self):
        """Unmute the microphone after speech is complete."""
        msg = String()
        msg.data = 'unmute'
        self.mic_control_publisher.publish(msg)
        logger.debug("Sent microphone unmute command")
    
    def signal_response_complete(self):
        """Signal that the entire response cycle (GPT + TTS + actions) is complete."""
        msg = String()
        msg.data = 'complete'
        self.response_complete_publisher.publish(msg)
        logger.info("📢 Signaled response cycle COMPLETE (microphone will unmute)")

    def query_callback(self, msg):
        """Handle incoming queries - only process the latest message."""
        user_query = msg.data.strip()
        current_time = time.time()
        
        # Filter out single words (likely transcription errors)
        words = user_query.split()
        if len(words) < 2:
            logger.info(f"Filtered single word query: '{user_query}' (likely transcription error)")
            return
        
        logger.info(f"Received user query: {user_query}")
        
        # Cancel any current processing task (only process latest message)
        if self.current_processing_task and not self.current_processing_task.done():
            logger.info("🚫 Cancelling previous query processing - new message received")
            self.current_processing_task.cancel()
        
        # Update latest message tracking
        self.latest_message = user_query
        self.latest_message_timestamp = current_time
        
        # Schedule processing of the latest message
        try:
            loop = asyncio.get_running_loop()
            self.current_processing_task = loop.create_task(self.process_latest_query_async())
        except RuntimeError:
            # No event loop running, use thread-safe call
            if hasattr(self, '_loop') and self._loop:
                self.current_processing_task = asyncio.run_coroutine_threadsafe(
                    self.process_latest_query_async(), self._loop
                )
            else:
                logger.warning("No asyncio event loop available, processing synchronously")
                # Fallback to synchronous processing
                import threading
                thread = threading.Thread(target=self._sync_process_query, args=(user_query,))
                thread.daemon = True
                thread.start()
    
    def _sync_process_query(self, user_query: str):
        """Synchronous fallback for query processing."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.process_query_async(user_query))
        except Exception as e:
            logger.error(f"Error in synchronous query processing: {e}")
        finally:
            loop.close()
    
    async def process_latest_query_async(self):
        """Process the latest message only - cancels if newer message arrives."""
        if not self.latest_message:
            logger.warning("No latest message to process")
            return
        
        user_query = self.latest_message
        message_timestamp = self.latest_message_timestamp
        
        logger.info(f"🎯 Processing LATEST message: '{user_query}'")
        
        try:
            await self.process_query_async(user_query, message_timestamp)
        except asyncio.CancelledError:
            logger.info("🚫 Query processing cancelled - newer message received")
            raise
        except Exception as e:
            logger.error(f"Error processing latest query: {e}")
    
    async def process_query_async(self, user_query: str, message_timestamp: float = None):
        """Process user query asynchronously with LLM and command execution."""
        async with self.processing_lock:
            try:
                # Check if this is still the latest message
                if message_timestamp and self.latest_message_timestamp and message_timestamp < self.latest_message_timestamp:
                    logger.info(f"🚫 Skipping outdated message: '{user_query}' (newer message available)")
                    return
                
                start_time = time.time()
                
                # Double-check we're still processing the latest message
                if self.latest_message != user_query:
                    logger.info(f"🚫 Message changed during processing, skipping: '{user_query}'")
                    return
                
                # Get GPT-4 response
                response = await self.get_gpt4_response_async(user_query)
                
                # Check again if we're still processing the latest message
                if self.latest_message != user_query:
                    logger.info(f"🚫 Message changed after GPT response, skipping execution: '{user_query}'")
                    return
                
                # Publish response
                await self.publish_response(response)
                
                # Parse and queue robot commands
                commands_queued = await self.parse_and_queue_commands(response)
                
                processing_time = time.time() - start_time
                logger.info(f"Query processed in {processing_time:.2f}s: '{user_query}' -> '{response}'")
                
                # If no commands were queued, signal completion immediately
                if not commands_queued:
                    logger.info("No commands queued, signaling immediate completion")
                    self.signal_response_complete()
                
            except asyncio.CancelledError:
                logger.info(f"🚫 Query processing cancelled: '{user_query}'")
                raise
            except Exception as e:
                logger.error(f"Error processing query '{user_query}': {e}")
                # Signal completion even on error to unmute microphone
                self.signal_response_complete()
    
    async def get_gpt4_response_async(self, query: str) -> str:
        """Get GPT-4 response asynchronously with improved prompting."""
        try:
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": query})
            
            # Keep conversation history manageable
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-8:]


            """
            TODO: the system_prompt variable will contain the prompt given to the LLM(GPT-4o)
            Your task is to write it. We want pupper to be able to understand commands given to it (which will be in natural conversation)
            e.g. "Walk forwards", "Bark for me Pupper", "turn anticlockwise", "do a little dance", "come forwards and turn left"
            and convert them into tool calls, e.g. [move], [bark], [turn left], [wiggle], [move, turn_left]
            Don't worry about making this prompt too long - the TA version is 50 lines!
            """
            # Enhanced system prompt for better command recognition
            system_prompt = """You are Pupper....... <complete the rest!>"""
            
            messages = [{"role": "system", "content": system_prompt}] + self.conversation_history
            
            # Make async API call
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=GPT_MODEL,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE
                )
            )
            
            gpt4_response = response.choices[0].message.content
            
            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": gpt4_response})
            
            return gpt4_response

        except Exception as e:
            logger.error(f"Error calling GPT-4 API: {e}")
            return "Sorry, I couldn't process your request due to an error. [stop]"
    
    async def publish_response(self, response: str):
        """Publish response to ROS2 topic."""
        response_msg = String()
        response_msg.data = response
        self.response_publisher.publish(response_msg)
        logger.info(f"Published GPT-4 response: {response}")
    
    async def parse_and_queue_commands(self, response: str) -> bool:
        """Parse response and queue appropriate robot commands. Returns True if commands were queued."""
        response_lower = response.lower()
        commands_queued = False
        
        # Extract commands from brackets if present
        import re
        bracket_match = re.search(r'\[([^\]]+)\]', response_lower)
        if bracket_match:
            commands_text = bracket_match.group(1)
            logger.info(f"📋 Extracted commands from brackets: '{commands_text}'")
        else:
            commands_text = response_lower
            logger.warning(f"⚠️  No bracket command found in response: '{response}'")
        
        # Queue speak command first (robot talks before acting)
        speak_text = re.sub(r'\[.*?\]', '', response).strip()
        if speak_text:
            speak_cmd = SpeakCommand(speak_text, self)  # Pass node reference
            await self.add_command(speak_cmd)
            commands_queued = True
        
        # Split commands by comma, but be smart about JSON (don't split inside {})
        command_list = self._split_commands(commands_text)
        logger.info(f"🎯 Parsed {len(command_list)} command(s): {command_list}")
        
        # Process each command
        for command_text in command_list:
            command_text = command_text.strip()
            if not command_text:
                continue
            
            queued = await self._queue_single_command(command_text)
            if queued:
                commands_queued = True
        
        # Add a completion signal command as the last command
        if commands_queued:
            completion_cmd = CompletionSignalCommand(self)
            await self.add_command(completion_cmd)
        
        return commands_queued
    
    def _split_commands(self, commands_text: str) -> list:
        """Split command text by commas, but preserve JSON objects."""
        commands = []
        current = ""
        depth = 0
        
        for char in commands_text:
            if char == '{':
                depth += 1
                current += char
            elif char == '}':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                # Only split on commas outside of JSON objects
                if current.strip():
                    commands.append(current.strip())
                current = ""
            else:
                current += char
        
        # Add the last command
        if current.strip():
            commands.append(current.strip())
        
        return commands
    
    async def _queue_single_command(self, command_text: str) -> bool:
        """Queue a single robot command. Returns True if command was queued."""
        # First check if there's a JSON velocity specification
        import re
        json_match = re.search(r'move\s*(\{[^}]+\})', command_text)
        
        if json_match:
            # Parse JSON velocity parameters
            try:
                velocity_json = json_match.group(1)
                velocities = json.loads(velocity_json)
                x = float(velocities.get('x', 0.0))
                y = float(velocities.get('y', 0.0))
                z = float(velocities.get('z', 0.0))
                logger.info(f'Queueing generic move command: x={x}, y={y}, z={z}')
                await self.add_command(GenericMoveCommand(x, y, z))
                return True
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f'Failed to parse velocity JSON: {e}, defaulting to stop')
                await self.add_command(KarelMethodCommand('stop', 'stop', duration=0.5))
                return True
        # Check for specific simple commands
        # TODO: Implement if statements for the pupper commands. "move" is done for you as an example.
        elif "move" in command_text:
            logger.info('Queueing command: Move forward')
            await self.add_command(KarelMethodCommand('move_forward', 'move forward', duration=1.5))
            return True
        elif "wiggle" in command_text or "dance" in command_text:
            logger.info('Queueing command: Wiggle')
            # Wiggle takes ~5 seconds in the karel API, add buffer
            await self.add_command(KarelMethodCommand('wiggle', 'wiggle', duration=6.0))
            return True
        elif "bark" in command_text:
            logger.info('Queueing command: Bark')
            # Bark plays audio, give it time to complete
            await self.add_command(KarelMethodCommand('bark', 'bark', duration=2.0))
            return True
        elif "stop" in command_text:
            logger.info('Queueing command: Stop')
            await self.add_command(KarelMethodCommand('stop', 'stop', duration=0.5))
            return True
        else:
            logger.info('No specific robot command found, defaulting to stop')
            await self.add_command(KarelMethodCommand('stop', 'stop', duration=0.5))
            return True
    
    def start_command_processor(self):
        """Start the background command queue processor."""
        if not self.queue_running:
            self.queue_running = True
            self.queue_task = asyncio.create_task(self._process_command_queue())
            logger.info("Command queue processor started")
    
    async def _process_command_queue(self):
        """Background task that processes commands from the queue sequentially."""
        while self.queue_running:
            try:
                # Wait for a command with timeout
                command = await asyncio.wait_for(self.command_queue.get(), timeout=0.1)
                logger.info(f"Executing command: {command.name}")
                
                # Create a cancellable task for command execution
                self.current_command_task = asyncio.create_task(command.execute(self.pupper))
                
                try:
                    success, message = await self.current_command_task
                    if success:
                        logger.info(f"Command {command.name} succeeded: {message}")
                    else:
                        logger.error(f"Command {command.name} failed: {message}")
                
                except asyncio.CancelledError:
                    logger.info(f"Command {command.name} was cancelled")
                    # Ensure robot is stopped after cancellation
                    try:
                        self.pupper.stop()
                    except:
                        pass
                
                except Exception as e:
                    logger.error(f"Error executing command {command.name}: {e}")
                finally:
                    self.current_command_task = None
            
            except asyncio.TimeoutError:
                # Timeout is expected, continue loop
                continue
            except Exception as e:
                logger.error(f"Unexpected error in command queue processor: {e}")
    
    async def add_command(self, command: Command) -> None:
        """Add a command to the queue."""
        await self.command_queue.put(command)
        logger.info(f"Added command {command.name} to queue")
    
    def stop_processing(self):
        """Stop command processing."""
        self.queue_running = False
        if self.queue_task:
            self.queue_task.cancel()
        if self.current_command_task:
            self.current_command_task.cancel()
        logger.info("Command processing stopped")

async def main_async(args=None):
    """Async main function with proper ROS2 and asyncio integration."""
    rclpy.init(args=args)

    # Create the enhanced GPT commander node
    commander_node = EnhancedGPTCommanderNode()
    
    # Store the event loop reference in the node for thread-safe access
    commander_node._loop = asyncio.get_running_loop()
    
    # Set up ROS2 executor
    executor = SingleThreadedExecutor()
    executor.add_node(commander_node)
    
    try:
        logger.info("Starting Enhanced GPT Commander Node...")
        logger.info("Features:")
        logger.info("  - Async LLM processing")
        logger.info("  - Command queue system")
        logger.info("  - OpenAI TTS integration")
        logger.info("  - Improved conversation handling")
        logger.info("Listening for user queries...")
        
        # Run ROS2 executor in asyncio-compatible way
        while rclpy.ok():
            # Spin once with timeout to allow asyncio tasks to run
            executor.spin_once(timeout_sec=0.1)
            await asyncio.sleep(0.01)  # Allow other async tasks to run
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Clean shutdown
        commander_node.stop_processing()
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
