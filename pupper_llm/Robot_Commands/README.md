# Keyword Spotting Robot Control

This repository contains a Python-based keyword spotting system designed to control a robot. It listens to specific voice commands and performs actions such as moving the robot or stopping it based on recognized keywords. The system uses pre-trained neural networks for real-time speech recognition.

## Features

- **Real-time Keyword Spotting**: Detects specific commands like "go", "left", "right", etc., using a microphone input.
- **Pre-trained Models**: Offers a choice between two models for inference, each with different characteristics:
  - **CNN Model**: Slightly higher accuracy at 94.6% but has more parameters.
  - **ResNet Model**: Slightly lower accuracy at 94.1% but has far fewer parameters, making it more lightweight.

## Models

The system includes two pre-trained models for keyword recognition:

1. **CNN Model**:
   - **Accuracy**: 94.6%
   - **Parameters**: 1.4 million
   - **Pros**: Higher accuracy.
   - **Cons**: More parameters, hence a larger file size.

2. **ResNet Model**:
   - **Accuracy**: 94.1%
   - **Parameters**: 359K
   - **Pros**: Lighter with fewer parameters, faster in low-resource environments.
   - **Cons**: Slightly lower accuracy.

The user can choose between these two models based on the requirements (e.g., accuracy vs. speed).

## Allowed Commands

The system recognizes and responds to the following set of allowed keywords:

- `go`
- `left`
- `right`
- `down`
- `stop`
- `up`
- `off`

In addition to these commands, the program can detect several other keywords for classification, but the robot will only respond to the commands listed above.

## Installation

To get started with this repository, clone the repository and install the required dependencies using the provided `requirements.txt` file.

### MacOS

```bash
brew install portaudio
````

### Install Required Modules:

```bash
pip install -r requirements.txt
```

## Running the System

### Step 1: Choose the Model

Choose the pre-trained model (either CNN or ResNet):

### Step 2: Set the Input Device

You can select an input audio device (such as a microphone) for real-time audio streaming. If you're unsure which device to use, you can list available input devices.


### Step 3: Start Streaming

Once you've selected the model and input device, you can press enter to start streaming.

The system will begin listening for the allowed keywords and trigger the corresponding commands in real time.

## Keyword Spotting System Flow

1. **Initialization**:
   - The system loads a pre-trained model (CNN or ResNet) from the specified path.
   - Audio input is captured from the microphone using `pyaudio` or `sounddevice`, and the audio is segmented into chunks of 0.9 seconds for processing.

2. **Feature Extraction**:
   - The audio signal is processed using `logfbank` to extract Mel-frequency log-filter bank features.

3. **Keyword Detection**:
   - The extracted features are passed to the pre-trained model to predict the probability of each keyword.
   - If a valid keyword is detected with a probability above the threshold (default: 98%), the command is executed.

4. **Command Execution**:
   - The system performs the robot control action based on the detected command (e.g., "go", "stop", "left", "right", etc.).
   - Two successive commands "off" followed by "stop" will terminate the program.

## Contributing

If you want to contribute to the project, feel free to fork the repository and submit a pull request. Make sure to follow best practices when modifying the code or adding new features.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

