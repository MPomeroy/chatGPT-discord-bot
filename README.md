# ChatGPT Discord Bot

> ### Build your own Discord bot with multiple AI providers

---
> [!IMPORTANT]
>
> **Major Refactor (2025/07):**
> - **5 AI Providers**: Free (g4f), OpenAI, Claude, Gemini, Grok
> - **No Cookie Authentication**: Removed unreliable cookie-based auth for free providers

### Chat

![image](https://user-images.githubusercontent.com/89479282/206497774-47d960cd-1aeb-4fba-9af5-1f9d6ff41f00.gif)

# Setup
## Prerequisites
* **Python 3.9 or later**
* **Rename the file `.env.example` to `.env`**
* Running `pip3 install -r requirements.txt` to install the required dependencies
* Optional: API keys for premium providers (OpenAI, Claude, Gemini, Grok)
---
## Step 1: Create a Discord bot

1. Go to https://discord.com/developers/applications create an application
2. Build a Discord bot under the application
3. Get the token from bot setting

   ![image](https://user-images.githubusercontent.com/89479282/205949161-4b508c6d-19a7-49b6-b8ed-7525ddbef430.png)
4. Store the token to `.env` under the `DISCORD_BOT_TOKEN`

   <img height="190" width="390" alt="image" src="https://user-images.githubusercontent.com/89479282/222661803-a7537ca7-88ae-4e66-9bec-384f3e83e6bd.png">

5. Turn MESSAGE CONTENT INTENT `ON`

   ![image](https://user-images.githubusercontent.com/89479282/205949323-4354bd7d-9bb9-4f4b-a87e-deb9933a89b5.png)

6. Invite your bot to your server via OAuth2 URL Generator

   ![image](https://user-images.githubusercontent.com/89479282/205949600-0c7ddb40-7e82-47a0-b59a-b089f929d177.png)



## Step 2: Run the bot on the desktop

1. Open a terminal or command prompt

2. Navigate to the directory where you installed the ChatGPT Discord bot

3. Run `python3 main.py` or `python main.py` to run the bot
---
## Step 2: Run the bot with Docker

1. Build the Docker image & run the Docker container with `docker compose up -d`

2. Inspect whether the bot works well `docker logs -t chatgpt-discord-bot`

   ### Stop the bot:

   * `docker ps` to see the list of running services
   * `docker stop <BOT CONTAINER ID>` to stop the running bot

### Have a good chat!
---

## Provider Configuration

### Free Provider (unstable)
Outdated model, close to GPT-3.5 or GPT-4 capabilities

No configuration required

### Premium Providers (Optional)

#### OpenAI
1. Obtain your API key from https://platform.openai.com/api-keys
2. Add to `.env`: `OPENAI_KEY=your_api_key_here`

#### Claude (Anthropic)
1. Get API key from https://console.anthropic.com/
2. Add to `.env`: `CLAUDE_KEY=your_api_key_here`

#### Gemini (Google)
1. Get API key from https://ai.google.dev/
2. Add to `.env`: `GEMINI_KEY=your_api_key_here`

#### Grok (xAI)
1. Get API key from https://x.ai/api
2. Add to `.env`: `GROK_KEY=your_api_key_here`

Use `/provider` command in Discord to switch between available providers

## Image Generation

<img src="https://i.imgur.com/Eo1ZzKk.png" width="300" alt="image">

Image generation is now integrated with the provider system:

### OpenAI DALL-E 3
- Requires OpenAI API key
- High-quality image generation
- Use `/draw [prompt] openai`

### Google Gemini
- Requires Gemini API key  
- Free tier available
- Use `/draw [prompt] gemini`

### Fallback Options
- If premium providers are unavailable, the bot will attempt to use free alternatives
- Image generation capabilities vary by provider availability

## Optional: Setup system prompt

* A system prompt would be invoked when the bot is first started or reset
* You can set it up by modifying the content in `system_prompt.txt`
* All the text in the file will be fired as a prompt to the bot
* Get the first message from ChatGPT in your discord channel!
* Go Discord setting turn `developer mode` on

   1. Right-click the channel you want to recieve the message, `Copy  ID`

        ![channel-id](https://user-images.githubusercontent.com/89479282/207697217-e03357b3-3b3d-44d0-b880-163217ed4a49.PNG)

   2. paste it into `.env` under `DISCORD_CHANNEL_ID`

## Optional: Disable logging

* Set the value of `LOGGING` in the `.env` to False

## Commands

### Core Commands
* `/chat [message]` - Chat with the current AI provider
* `/provider` - Switch between AI providers (Free, OpenAI, Claude, Gemini, Grok)
* `/draw [prompt] [model]` - Generate images with specified provider
* `/reset` - Clear conversation history
* `/help` - Display all available commands

### Voice Commands
* `/join` - Join your current voice channel
* `/leave` - Leave the voice channel
* `/voicestatus` - Show voice connection status
* `/togglevoice` - Toggle voice features on/off

### Persona Commands
* `/switchpersona [persona]` - Switch AI personality (admin-only for jailbreaks)
   * `standard` - Standard helpful assistant
   * `creative` - More creative and imaginative responses  
   * `technical` - Technical and precise responses
   * `casual` - Casual and friendly tone
   * `jailbreak-v1` - BYPASS mode (admin only)
   * `jailbreak-v2` - SAM mode (admin only)
   * `jailbreak-v3` - Developer Mode Plus (admin only)

### Bot Behavior
* `/private` - Bot replies only visible to command user
* `/public` - Bot replies visible to everyone (default)
* `/replyall` - Bot responds to all messages in channel (toggle)

## Voice Channel Features

The bot can now join voice channels and interact with users through voice! It automatically joins when users enter a voice channel and leaves when everyone exits.

### Features
* **Automatic Join**: Bot automatically joins voice channels when users join
* **Voice Activity Detection**: Processes audio when user stops speaking
* **Turn-Based Conversation**: Bot ignores user audio while speaking (prevents interruptions)
* **Audio Processing**: Uses OpenAI's gpt-audio model for audio-to-audio responses
* **Fallback Support**: Falls back to Whisper + GPT + TTS if gpt-audio unavailable

### Configuration

Add these environment variables to your `.env` file:

```env
# Voice Features
VOICE_ENABLED=True                    # Enable/disable voice features (default: True)
VOICE_AUTO_JOIN=True                  # Auto-join when users join channels (default: True)
VOICE_SILENCE_DURATION=1.5            # Seconds of silence before processing (default: 1.5)
AUDIO_SAMPLE_RATE=48000               # Audio quality setting (default: 48000)
```

### Requirements

Voice features require additional dependencies:
* **discord-ext-voice-recv** - Voice recording extension for discord.py
* **PyNaCl** - Discord voice support
* **pydub** - Audio processing
* **FFmpeg** - Audio codec (must be installed on system)

All dependencies are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Install FFmpeg:
* **Windows**: Download from https://ffmpeg.org/ and add to PATH
* **Linux**: `sudo apt install ffmpeg`
* **macOS**: `brew install ffmpeg`

### Usage

1. Make sure `VOICE_ENABLED=True` in your `.env` file
2. The bot will automatically join voice channels when users join (if `VOICE_AUTO_JOIN=True`)
3. Speak into your microphone - the bot listens continuously
4. When you stop speaking (1.5s silence), it processes your audio
5. The bot responds with audio in the voice channel

Alternatively, use `/join` to manually connect to your current voice channel.

### Technical Details

The implementation uses:
* **OpenAI gpt-audio model** via `/v1/completions` API for audio-to-audio processing
* **Opus decoder** - Decodes Discord's Opus audio to PCM/WAV format
* **discord-ext-voice-recv** - Captures voice data from Discord
* **Multiple API format approaches** - The exact API format is flexible to accommodate future changes
* **Fallback pipeline** - If gpt-audio is unavailable, uses Whisper (transcription) + GPT (response) + TTS (speech)

**Audio Pipeline**:
1. Users speak → Discord captures Opus audio (48kHz stereo)
2. Bot decodes Opus to PCM and converts to WAV
3. WAV sent to OpenAI gpt-audio model
4. Audio response played back via FFmpeg

**Note**: The gpt-audio model format with v1/completions is not fully documented in public OpenAI docs. The implementation includes flexible stubs that can be adjusted when the exact API format is confirmed.

## Security Features

### Admin-Only Jailbreak Access
Jailbreak personas require admin privileges for enhanced security:

1. Set `ADMIN_USER_IDS` in `.env` with comma-separated Discord user IDs
2. Only admin users can access jailbreak personas
3. Regular users see only safe personas in `/switchpersona`

> **Warning**
> Jailbreak personas may generate content that bypasses normal AI safety measures. Admin access required.

### Environment Security
- No cookie-based authentication (removed for reliability)
- Secure API key management via environment variables
- Docker security hardening with non-root user
- Read-only filesystem for container security
