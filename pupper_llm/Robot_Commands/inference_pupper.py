import sounddevice as sd
import numpy as np
import wave
import tensorflow as tf
from python_speech_features import logfbank
import os
from queue import Queue

commands = [
    'backward', 'bed', 'bird', 'cat', 'dog', 'down', 'eight', 'five', 'follow',
    'forward', 'four', 'go', 'happy', 'house', 'learn', 'left', 'marvin', 'nine',
    'no', 'off', 'on', 'one', 'right', 'seven', 'sheila', 'six', 'stop', 'three',
    'tree', 'two', 'up', 'visual', 'wow', 'yes', 'zero'
]

class_to_label = {i: commands[i] for i in range(len(commands))}

stop_by_voice = True

class KeywordSpotting:
    def __init__(self, model_path, prob_threshold=0.90):
        # Load pre-trained model
        self.model = self.load_model(model_path)

        self.RATE = 16000  # Sample rate in Hz
        self.CHUNK_DURATION = 0.9  # Size of the chunk window, in seconds
        self.CHUNK = int(self.CHUNK_DURATION * self.RATE)  # Audio samples per frame

        self.queue = Queue()
        self.classification_threshold = prob_threshold
        self.last_2_kw = ['', '']

    def record_audio(self, filename):
        """Record audio using sounddevice and save it to a .wav file."""
        print(f"Recording audio for {self.CHUNK_DURATION} seconds...")

        # Record the audio
        recording = sd.rec(int(self.CHUNK_DURATION * self.RATE), samplerate=self.RATE, channels=1, dtype=np.int16)
        sd.wait()  # Wait until recording is finished

        # Save the recorded data to a wav file
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)  # Mono channel
            wf.setsampwidth(2)  # 16-bit samples (2 bytes per sample)
            wf.setframerate(self.RATE)  # Set the frame rate to 16kHz
            wf.writeframes(recording.tobytes())  # Save as byte data

        print(f"Recording saved to {filename}")

    def process_audio(self, filename):
        """Process the recorded audio and pass it to the model."""
        # Load the recorded audio
        with wave.open(filename, 'r') as wf:
            audio = wf.readframes(self.CHUNK)
            audio = np.frombuffer(audio, dtype=np.int16)

        # Extract logfbank features
        data_fb = logfbank(
            audio,
            samplerate=self.RATE,
            winlen=25/1000,
            winstep=10/1000,
            nfilt=40,
            nfft=512,
            lowfreq=300,
            highfreq=None,
        ).T

        # Detect the keyword
        is_keyword, i_kw, kw, kw_prob, probabilities = self.spot_keyword(data_fb)

        if is_keyword:
            print(f'KW: {kw}\nProbability: {kw_prob * 100:.1f}%')

            self.last_2_kw.pop(0)
            self.last_2_kw.append(kw)

        # Stop by vocal command
        if stop_by_voice and ' '.join(self.last_2_kw) == 'off stop':
            print('Process closed')
            sys.exit(0)

    def spot_keyword(self, input_data):
        """Spot a keyword in the current chunk."""
        num_frames = input_data.shape[1]
        
        # Pad the input data to have 99 frames if it's shorter, or truncate if it's longer
        target_frames = 99
        if num_frames < target_frames:
            # Pad with zeros if there are fewer than 99 frames
            padding = np.zeros((input_data.shape[0], target_frames - num_frames))
            input_data = np.hstack((input_data, padding))
        elif num_frames > target_frames:
            # Truncate if there are more than 99 frames
            input_data = input_data[:, :target_frames]

        # Reshape the input data for the model
        input_data = tf.reshape(input_data, (1, target_frames, 40, 1))

        # Predict using the model
        prediction = self.model.predict(input_data, verbose=0).reshape(-1)

        i_kw = np.argmax(prediction)
        is_kw = False
        valid_keywords = ["go", "left", "right", "stop", "up"]

        if prediction[i_kw] > self.classification_threshold:
            kw = class_to_label[i_kw]
            if kw in valid_keywords:
                is_kw = True

        output = kw if is_kw else None
        return is_kw, i_kw, output, prediction[i_kw], prediction * 100

    @staticmethod
    def load_model(model_path):
        """Load the pre-trained model."""
        return tf.keras.models.load_model(model_path, compile=False)


if __name__ == "__main__":
    models_path = "models"

    # Get available models
    models_dict = {}
    for file in os.listdir(models_path):
        if file.endswith(".keras"):
            models_dict[len(models_dict)] = file

    # Print available models
    print("\nAvailable models:")
    for key, value in models_dict.items():
        print(key, ':', value)

    # Input model
    model_index = input('\n- Insert input model index and press Enter to continue\n... ')
    model_name = models_dict[int(model_index)]

    ks_streaming = KeywordSpotting(os.path.join(models_path, model_name).replace("\\", "/"))

    # Continuously record and process audio
    audio_filename = "recorded_audio.wav"

    try:
        while True:
            ks_streaming.record_audio(audio_filename)
            ks_streaming.process_audio(audio_filename)

    except KeyboardInterrupt:
        print("\nProcess terminated by user.")
        sys.exit(0)
