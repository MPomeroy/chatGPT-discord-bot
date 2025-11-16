# Voice Features Setup Guide

## Quick Start

The voice features have been successfully implemented using `discord.py` with the `discord-ext-voice-recv` extension for voice recording support!

## Installation Steps

### 1. Install Dependencies

All required dependencies are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

This includes:
- `discord.py` - Main Discord library
- `discord-ext-voice-recv` - Voice recording extension
- `PyNaCl` - Voice encryption
- `pydub` - Audio processing
- Other dependencies

### 2. Install FFmpeg

Voice features require FFmpeg for audio processing:

**Windows:**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract the archive
3. Add the `bin` folder to your system PATH
4. Restart your terminal

**Linux:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

### 3. Configure Environment

Add these to your `.env` file:

```env
# Voice Features
VOICE_ENABLED=True
VOICE_AUTO_JOIN=True
VOICE_SILENCE_DURATION=1.5
AUDIO_SAMPLE_RATE=48000

# OpenAI API Key (required for audio processing)
OPENAI_KEY=your_openai_api_key_here
```

### 4. Enable Voice Intents

Make sure your Discord bot has the following intents enabled in the Discord Developer Portal:
- Message Content Intent (already enabled)
- Voice State Intent (should already be configured by the code)

## How It Works

### Automatic Mode (Default)
1. When a user joins a voice channel, the bot automatically joins
2. The bot listens for voice input (👂 Listening)
3. When you stop speaking (1.5s silence), it processes your audio
4. The bot responds with audio in the voice channel (🔊 Speaking)
5. **While speaking, bot ignores all incoming audio** (turn-based conversation)
6. When audio playback finishes, bot resumes listening
7. When all users leave, the bot automatically disconnects

### Manual Commands

- `/join` - Manually join your current voice channel
- `/leave` - Leave the current voice channel
- `/voicestatus` - Check voice connection status
- `/togglevoice` - Enable/disable voice features

## Audio Processing

The implementation uses OpenAI's `gpt-audio` model with a flexible API format:

1. **Primary Method**: Direct gpt-audio model via completions API
2. **Fallback Pipeline**: If gpt-audio fails, uses Whisper (transcription) → GPT (response) → TTS (speech)

## Troubleshooting

### Error: "discord.sinks not available" or "voice_recv not available"
**Solution:** Make sure discord-ext-voice-recv is installed:
```bash
pip install discord-ext-voice-recv
```

### Error: "FFmpeg not found"
**Solution:** Install FFmpeg and make sure it's in your system PATH

### Bot joins but doesn't respond
**Possible causes:**
1. No OpenAI API key configured
2. FFmpeg not installed
3. Voice recording not working (check logs)

**Check logs for:**
- "Started recording in guild..." - Recording is working
- "Voice recording not supported" - Need to install py-cord

### Audio quality issues
Adjust these environment variables:
- `VOICE_SILENCE_DURATION` - Increase if bot cuts you off too early
- `AUDIO_SAMPLE_RATE` - 48000 is Discord's default, don't change unless needed

## Testing

1. Start the bot: `python main.py`
2. Join a voice channel in your Discord server
3. Bot should automatically join (if VOICE_AUTO_JOIN=True)
4. Speak into your microphone
5. Wait 1.5 seconds after finishing
6. Bot processes and responds with audio

Check the console logs for:
```
Started recording in guild...
Processing audio from user... 
Playing audio response in guild...
```

## Current Limitations

1. **Sequential Processing**: Bot processes one user at a time
2. **API Format**: gpt-audio format is not fully documented, uses flexible stubs
3. **Recording Quality**: Depends on Discord's Opus codec and your microphone

## Architecture

### Audio Processing Pipeline

```
User speaks → Discord (Opus 48kHz) → Opus Decoder → PCM → WAV → 
OpenAI gpt-audio API → Audio Response → FFmpeg → Discord Voice → User hears
```

**Detailed Steps**:
1. User speaks into microphone
2. Discord captures audio and encodes to Opus format (48kHz, stereo, 20ms frames)
3. Bot receives Opus frames via discord-ext-voice-recv
4. Opus frames buffered until silence detected (1.5s default)
5. Opus frames decoded to PCM using discord.opus decoder
6. PCM converted to WAV format
7. WAV sent to OpenAI's gpt-audio model
8. Audio response received and played via FFmpeg

**Files:**
- `src/voice_manager.py` - Voice connection, Opus decoding, audio buffering
- `src/audio_provider.py` - OpenAI audio API integration
- `src/aclient.py` - Discord client integration
- `src/bot.py` - Voice commands

## Need Help?

Check the logs in your terminal for detailed error messages and warnings. The bot will provide helpful suggestions when voice features aren't working properly.

