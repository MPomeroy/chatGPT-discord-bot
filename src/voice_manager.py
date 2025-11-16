import os
import asyncio
import discord
import io
import wave
import base64
import time
import struct
from typing import Dict, Optional, List
from collections import defaultdict
from src.log import logger

try:
    import discord.opus as opus_decoder
    OPUS_AVAILABLE = True
except (ImportError, OSError):
    OPUS_AVAILABLE = False
    logger.warning("Discord opus decoder not available")

# Check if discord.sinks is available (py-cord or discord.py with voice extras)
try:
    from discord.ext import voice_recv
    SINKS_AVAILABLE = True
except ImportError:
    SINKS_AVAILABLE = False
    logger.warning("discord.sinks not available. Voice recording features will be limited.")
    logger.info("For full voice support, install: pip install py-cord[voice] instead of discord.py")
    
    # Create a dummy Sink class as fallback
    class DiscordSink:
        """Fallback Sink implementation"""
        def __init__(self):
            pass


class AudioBuffer:
    """Buffer for collecting audio from a user until silence is detected"""
    
    def __init__(self, user_id: int, sample_rate: int = 48000):
        self.user_id = user_id
        self.sample_rate = sample_rate
        self.frames: List[voice_recv.VoiceData] = []
        self.last_audio_time = time.time()  # Use time.time() instead of event loop time
        self.silence_duration = float(os.getenv("VOICE_SILENCE_DURATION", "1.5"))
        
    def add_audio(self, data: voice_recv.VoiceData):
        """Add audio frame to buffer"""
        self.frames.append(data)
        self.last_audio_time = time.time()  # Use time.time() instead of event loop time
        
    def is_silent(self) -> bool:
        """Check if buffer has been silent long enough"""
        current_time = time.time()  # Use time.time() instead of event loop time
        return (current_time - self.last_audio_time) > self.silence_duration
    
    def has_audio(self) -> bool:
        """Check if buffer has any audio"""
        return len(self.frames) > 0
    
    def get_audio_data(self) -> List:
        """Get all audio frames (as VoiceData objects)"""
        return self.frames
    
    def clear(self):
        """Clear the buffer"""
        self.frames.clear()
        self.last_audio_time = time.time()  # Use time.time() instead of event loop time


class MyAudioSink(voice_recv.AudioSink):
    """Custom audio sink that captures audio from voice channels"""
    
    def __init__(self, voice_manager):
        super().__init__()
        self.voice_manager = voice_manager
    
    def write(self, user, data):
        """Called when audio data is received from a user"""
        if user and data:
            self.voice_manager.on_audio_received(user, data)
    
    def cleanup(self):
        """Cleanup when recording stops"""
        pass

    def wants_opus(self) -> bool:
        return True


class VoiceManager:
    """Manages voice channel connections and audio processing"""
    
    def __init__(self, discord_client):
        self.client = discord_client
        self.voice_connections: Dict[int, voice_recv.VoiceRecvClient] = {}  # guild_id -> VoiceClient
        self.audio_buffers: Dict[int, Dict[int, AudioBuffer]] = defaultdict(dict)  # guild_id -> user_id -> AudioBuffer
        self.processing_lock: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)  # guild_id -> Lock
        self.playing_audio: Dict[int, bool] = {}  # guild_id -> is_playing (track playback state)
        self.enabled = os.getenv("VOICE_ENABLED", "True") == "True"
        self.auto_join = os.getenv("VOICE_AUTO_JOIN", "True") == "True"
        self.sample_rate = int(os.getenv("AUDIO_SAMPLE_RATE", "48000"))
        self.audio_provider = None  # Will be set after initialization
        
        # Start background task to process audio buffers
        self.processing_task = None
        
    async def start_processing(self):
        """Start the background audio processing task"""
        if self.processing_task is None:
            self.processing_task = asyncio.create_task(self._process_audio_buffers())
            logger.info("Voice manager processing started")
    
    async def stop_processing(self):
        """Stop the background audio processing task"""
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
            self.processing_task = None
            logger.info("Voice manager processing stopped")
    
    def set_audio_provider(self, audio_provider):
        """Set the audio provider for processing"""
        self.audio_provider = audio_provider
        logger.info("Audio provider set for voice manager")
    
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state updates"""
        if not self.enabled or not self.auto_join:
            return
        
        # Ignore bot's own voice state changes
        if member.bot:
            return
        
        guild_id = member.guild.id
        
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            await self._handle_user_join(member, after.channel)
        
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            await self._handle_user_leave(member, before.channel)
        
        # User moved between channels
        elif before.channel != after.channel:
            if before.channel:
                await self._handle_user_leave(member, before.channel)
            if after.channel:
                await self._handle_user_join(member, after.channel)
    
    async def _handle_user_join(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user joining a voice channel"""
        guild_id = member.guild.id
        
        # If bot is not in this channel, join it
        if guild_id not in self.voice_connections:
            try:
                logger.info(f"User {member.name} joined {channel.name}, bot joining...")
                await self.join_voice_channel(channel)
            except Exception as e:
                logger.error(f"Failed to join voice channel: {e}")
    
    async def _handle_user_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """Handle user leaving a voice channel"""
        guild_id = member.guild.id
        
        # Check if there are any non-bot members left in the channel
        if guild_id in self.voice_connections:
            voice_client = self.voice_connections[guild_id]
            if voice_client.channel == channel:
                # Count non-bot members
                non_bot_members = [m for m in channel.members if not m.bot]
                if len(non_bot_members) == 0:
                    logger.info(f"No users left in {channel.name}, leaving...")
                    await self.leave_voice_channel(guild_id)
    
    async def join_voice_channel(self, channel: discord.VoiceChannel) -> bool:
        """Join a voice channel"""
        guild_id = channel.guild.id
        
        try:
            # Check if already connected
            if guild_id in self.voice_connections:
                logger.warning(f"Already connected to a voice channel in guild {guild_id}")
                return False
            
            # Connect to voice channel
            voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
            self.voice_connections[guild_id] = voice_client
            
            # Initialize playback state
            self.playing_audio[guild_id] = False
            
            # Start recording audio
            await self._start_recording(guild_id)
            
            logger.info(f"Successfully joined voice channel: {channel.name} in {channel.guild.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error joining voice channel: {e}")
            return False
    
    async def leave_voice_channel(self, guild_id: int) -> bool:
        """Leave a voice channel"""
        try:
            if guild_id not in self.voice_connections:
                logger.warning(f"Not connected to any voice channel in guild {guild_id}")
                return False
            
            voice_client = self.voice_connections[guild_id]
            
            # Stop recording if active
            try:
                if voice_client.is_recording():
                    voice_client.stop_recording()
            except (AttributeError, Exception) as e:
                logger.debug(f"Could not stop recording: {e}")
            
            # Disconnect
            await voice_client.disconnect()
            
            # Clean up
            del self.voice_connections[guild_id]
            if guild_id in self.audio_buffers:
                del self.audio_buffers[guild_id]
            if guild_id in self.playing_audio:
                del self.playing_audio[guild_id]
            
            logger.info(f"Left voice channel in guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error leaving voice channel: {e}")
            return False
    
    async def _start_recording(self, guild_id: int):
        """Start recording audio from the voice channel"""
        if guild_id not in self.voice_connections:
            return
        
        voice_client = self.voice_connections[guild_id]
        
        # Create custom sink
        sink = MyAudioSink(self)
        
        # Start recording
        if not SINKS_AVAILABLE:
            logger.warning(f"Cannot start recording in guild {guild_id}: discord.sinks not available")
            logger.info("Install py-cord for voice recording: pip uninstall discord.py && pip install py-cord[voice]")
            return
        
        try:
            voice_client.listen(
                sink,
                after=self._recording_callback,
            )
            logger.info(f"Started recording in guild {guild_id}")
        except AttributeError as e:
            # If start_recording doesn't exist, we need to listen differently
            logger.warning(f"Voice recording not supported: {e}")
            logger.info("Try installing py-cord instead: pip uninstall discord.py && pip install py-cord[voice]")
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
    
    def _recording_callback(self, sink, *args):
        """Callback when recording finishes"""
        logger.info(f"Recording finished.")
    
    def on_audio_received(self, user, audio_data: bytes):
        """Called when audio data is received from a user"""
        # Find which guild this audio is from
        guild_id = None
        for gid, vc in self.voice_connections.items():
            try:
                if vc.is_recording():
                    guild_id = gid
                    break
            except AttributeError:
                # is_recording might not exist
                guild_id = gid
                break
        
        if guild_id is None:
            return
        
        # Ignore audio if bot is currently playing (turn-based conversation)
        if self.playing_audio.get(guild_id, False):
            logger.debug(f"Ignoring audio in guild {guild_id} - bot is speaking")
            return
        
        user_id = user if isinstance(user, int) else user.id
        
        # Get or create buffer for this user
        if user_id not in self.audio_buffers[guild_id]:
            self.audio_buffers[guild_id][user_id] = AudioBuffer(user_id, self.sample_rate)
        
        # Add audio to buffer
        self.audio_buffers[guild_id][user_id].add_audio(audio_data)
    
    async def _process_audio_buffers(self):
        """Background task to process audio buffers when silence is detected"""
        while True:
            try:
                await asyncio.sleep(0.5)  # Check every 500ms
                
                # Process buffers for each guild
                for guild_id in list(self.audio_buffers.keys()):
                    async with self.processing_lock[guild_id]:
                        for user_id in list(self.audio_buffers[guild_id].keys()):
                            buffer = self.audio_buffers[guild_id][user_id]
                            
                            # Check if buffer has audio and is now silent
                            if buffer.has_audio() and buffer.is_silent():
                                # Process this audio
                                await self._process_user_audio(guild_id, user_id, buffer)
                                buffer.clear()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in audio buffer processing: {e}")
    
    async def _process_user_audio(self, guild_id: int, user_id: int, buffer: AudioBuffer):
        """Process audio from a user"""
        if not self.audio_provider:
            logger.warning("No audio provider set, skipping audio processing")
            return
        
        try:
            # Get audio frames
            audio_frames = buffer.get_audio_data()
            
            if len(audio_frames) < 5:  # Too short, likely noise (less than ~100ms)
                logger.debug(f"Audio too short from user {user_id}, skipping")
                return
            
            logger.info(f"Processing audio from user {user_id} ({len(audio_frames)} frames)")
            
            # Convert Opus frames to WAV format
            wav_data = self._opus_frames_to_wav(audio_frames, buffer.sample_rate)
            
            if not wav_data:
                logger.error("Failed to convert opus to WAV")
                return
            
            logger.info(f"Converted to WAV: {len(wav_data)} bytes")
            
            # Send to audio provider for processing
            response_audio = await self.audio_provider.process_audio(wav_data)
            
            # Play response back in voice channel
            if response_audio and guild_id in self.voice_connections:
                await self._play_audio_response(guild_id, response_audio)
            
        except Exception as e:
            logger.error(f"Error processing user audio: {e}")
    
    def _opus_frames_to_wav(self, voice_frames: List, sample_rate: int) -> Optional[bytes]:
        """
        Convert Opus-encoded VoiceData frames to WAV format.
        
        Args:
            voice_frames: List of VoiceData objects containing opus data
            sample_rate: Sample rate (Discord uses 48000)
            
        Returns:
            WAV file as bytes, or None if conversion fails
        """
        try:
            if not OPUS_AVAILABLE:
                logger.error("Opus decoder not available - cannot decode voice data")
                return None
            
            # Initialize Opus decoder
            # Discord uses Opus with 48kHz, stereo, 20ms frame size
            decoder = opus_decoder.Decoder()
            
            # Decode all Opus frames to PCM
            pcm_data = []
            for frame in voice_frames:
                try:
                    # Decode opus data to PCM (16-bit signed integers)
                    # Discord's opus frames are stereo, 48kHz
                    decoded = decoder.decode(frame.opus, fec=False)
                    pcm_data.append(decoded)
                except Exception as e:
                    logger.debug(f"Failed to decode frame: {e}")
                    continue
            
            if not pcm_data:
                logger.warning("No audio frames could be decoded")
                return None
            
            # Concatenate all PCM data
            full_pcm = b''.join(pcm_data)
            
            # Convert PCM to WAV format
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(full_pcm)
            
            wav_io.seek(0)
            return wav_io.read()
            
        except Exception as e:
            logger.error(f"Error converting Opus to WAV: {e}")
            return None
    
    async def _play_audio_response(self, guild_id: int, audio_data: bytes):
        """Play audio response in the voice channel"""
        if guild_id not in self.voice_connections:
            return
        
        voice_client = self.voice_connections[guild_id]
        
        try:
            # Save audio to temporary file
            temp_file = f"temp_audio_{guild_id}.wav"
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            
            # Create audio source
            audio_source = discord.FFmpegPCMAudio(temp_file)
            
            # Play audio
            if not voice_client.is_playing():
                # Set playing flag before starting playback
                self.playing_audio[guild_id] = True
                logger.info(f"Playing audio response in guild {guild_id}")
                
                # Play with callback to clear flag when done
                voice_client.play(
                    audio_source, 
                    bitrate=256,
                    after=lambda e: self._on_playback_complete(guild_id, temp_file, e)
                )
            else:
                logger.warning(f"Already playing audio in guild {guild_id}")
                # Clean up temp file since we won't play it
                self._cleanup_audio_file(temp_file, None)
                
        except Exception as e:
            logger.error(f"Error playing audio response: {e}")
            # Make sure to clear the flag if there's an error
            self.playing_audio[guild_id] = False
    
    def _on_playback_complete(self, guild_id: int, temp_file: str, error):
        """Callback when audio playback completes"""
        # Clear the playing flag - bot is now ready to listen again
        self.playing_audio[guild_id] = False
        logger.info(f"Audio playback complete in guild {guild_id} - ready to listen")
        
        # Clean up the temp file
        self._cleanup_audio_file(temp_file, error)
    
    def _cleanup_audio_file(self, filename: str, error):
        """Clean up temporary audio file after playback"""
        try:
            if error:
                logger.error(f"Error during audio playback: {error}")
            
            if os.path.exists(filename):
                os.remove(filename)
                logger.debug(f"Cleaned up temporary audio file: {filename}")
        except Exception as e:
            logger.error(f"Error cleaning up audio file: {e}")
    
    def get_status(self, guild_id: int) -> Dict:
        """Get voice connection status for a guild"""
        connected = guild_id in self.voice_connections
        
        status = {
            "connected": connected,
            "enabled": self.enabled,
            "auto_join": self.auto_join,
        }
        
        if connected:
            voice_client = self.voice_connections[guild_id]
            try:
                is_recording = voice_client.is_recording()
            except AttributeError:
                is_recording = False
            
            is_playing = self.playing_audio.get(guild_id, False)
            
            status.update({
                "channel": voice_client.channel.name if voice_client.channel else "Unknown",
                "recording": is_recording,
                "playing": is_playing,
                "listening": not is_playing,  # Bot listens when not playing
            })
        
        return status
    
    def is_connected(self, guild_id: int) -> bool:
        """Check if bot is connected to a voice channel in this guild"""
        return guild_id in self.voice_connections

