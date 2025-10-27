import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import sounddevice as sd
import numpy as np
import wave
import whisper as wh
import time

class CommandPublisher(Node):
    def __init__(self):
        super().__init__('command_publisher')

        # Create a publisher for the user query topic
        self.publisher_ = self.create_publisher(
            String,
            'user_query_topic',  # Topic name for publishing user queries
            10
        )
        self.get_logger().info('Command Line Publisher Node has started.')
        
        # Load Whisper model
        self.model = wh.load_model("tiny")  # Use other models like "base" or "small" if necessary

    def record_audio_to_wav(self, duration=5, sample_rate=16000, filename='recorded_audio.wav'):
        """Record audio and save it as a WAV file."""
        self.get_logger().info("Recording audio...")
        audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
        sd.wait()  # Wait until the recording is finished
        self.get_logger().info("Audio recording finished.")

        # Save the recorded audio as a WAV file
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit audio
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        self.get_logger().info(f"Audio saved as {filename}")
        return filename

    def transcribe_audio_with_whisper(self, filename):
        """Transcribe audio using Whisper."""
        try:
            self.get_logger().info("Transcribing audio using Whisper...")
            result = self.model.transcribe(filename)
            self.get_logger().info(f"Transcription: {result['text']}")
            return result['text']
        except Exception as e:
            self.get_logger().error(f"Error during transcription: {e}")
            return None

    def publish_message(self, message):
        """Create a String message and publish it."""
        msg = String()
        msg.data = message
        self.publisher_.publish(msg)
        self.get_logger().info(f"Published message: {message}")

    def main_loop(self):
        """Main loop to continuously record, transcribe, and publish audio."""
        while rclpy.ok():
            # Record 5 seconds of audio and save to a WAV file
            wav_file = self.record_audio_to_wav(duration=5)

            # Transcribe the saved WAV file using Whisper
            transcription = self.transcribe_audio_with_whisper(wav_file)

            # Publish the transcription if it's not empty
            if transcription:
                self.publish_message(transcription)

            # Delay before the next recording (optional)
            time.sleep(0.9)


def main(args=None):
    # Initialize the ROS2 Python client library
    rclpy.init(args=args)

    # Create the command line publisher node
    command_publisher = CommandPublisher()

    # Run the main loop to record, transcribe, and publish audio
    try:
        command_publisher.main_loop()
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting...")

    # Clean up and shutdown
    command_publisher.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
