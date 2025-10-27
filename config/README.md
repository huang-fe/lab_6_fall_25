# API Configuration

This directory contains the centralized API key configuration for the Pupper LLM system.

## Quick Setup

Run the setup script from the project root:

```bash
cd /home/pi/lab_6_fall_2025_solutions
python3 setup_api_keys.py
```

## Manual Setup

1. Copy the template file:
   ```bash
   cp config/api_keys_template.py config/api_keys.py
   ```

2. Edit `config/api_keys.py` and replace `your-openai-api-key-here` with your actual OpenAI API key.

## Environment Variable Setup (Recommended for Production)

Set the environment variable:
```bash
export OPENAI_API_KEY='your-actual-api-key-here'
```

Add to your `~/.bashrc` for persistence:
```bash
echo 'export OPENAI_API_KEY="your-actual-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

## Configuration Options

The `api_keys.py` file contains:

- **OPENAI_API_KEY**: Your OpenAI API key
- **GPT_MODEL**: GPT model to use (default: "gpt-4")
- **WHISPER_MODEL**: Whisper model for transcription (default: "whisper-1")
- **TTS_MODEL**: Text-to-speech model (default: "tts-1")
- **TTS_VOICE**: Voice for TTS (default: "alloy")
- **MAX_TOKENS**: Maximum tokens for GPT responses (default: 150)
- **TEMPERATURE**: Creativity setting for GPT (default: 0.7)

## Security Notes

- ⚠️ **Never commit `api_keys.py` to version control**
- 🔒 Keep your API keys secure and don't share them
- 🔄 Rotate keys regularly for security
- 🌍 Use environment variables for production deployments

## Testing Configuration

Test your configuration:
```bash
cd /home/pi/lab_6_fall_2025_solutions/config
python3 api_keys.py
```

This will validate your API key format and show your configuration settings.

## Files

- `api_keys_template.py` - Template file (safe to commit)
- `api_keys.py` - Your actual configuration (DO NOT COMMIT)
- `README.md` - This documentation

## Troubleshooting

### "No OpenAI API key found" Error

1. Make sure you've created `config/api_keys.py` from the template
2. Verify your API key is correctly set in the file
3. Or set the `OPENAI_API_KEY` environment variable

### "API key validation failed" Error

1. Check that your API key starts with `sk-`
2. Verify the key is copied correctly (no extra spaces)
3. Test the key at https://platform.openai.com/

### Import Errors

Make sure you're running scripts from the correct directory. The scripts automatically add the config directory to the Python path.

