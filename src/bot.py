import os
import asyncio
import discord
from discord import app_commands
from typing import Optional

from src.aclient import discordClient
from src.providers import ProviderType
from src import log, personas
from src.log import logger
from src import reasoning_config


def run_discord_bot():
    @discordClient.event
    async def on_ready():
        await discordClient.send_start_prompt()
        
        # Sync commands - guild sync is instant, global sync takes up to 1 hour
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            # Guild-specific sync (instant) - good for development
            guild = discord.Object(id=int(guild_id))
            discordClient.tree.copy_global_to(guild=guild)
            await discordClient.tree.sync(guild=guild)
            logger.info(f"Commands synced to guild {guild_id}")
        else:
            # Global sync (can take up to 1 hour)
            await discordClient.tree.sync()
            logger.info("Commands synced globally (may take up to 1 hour to appear)")
        
        loop = asyncio.get_event_loop()
        loop.create_task(discordClient.process_messages())
        logger.info(f'{discordClient.user} is now running!')

    @discordClient.tree.command(name="draw", description="Generate an image")
    async def draw(interaction: discord.Interaction, *, prompt: str):
        # Input validation
        prompt = prompt.strip()
        if not prompt:
            await interaction.response.send_message(
                "❌ Please provide a prompt", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Generate image using current provider
            image_url = await discordClient.generate_image(prompt)
            
            embed = discord.Embed(
                title="🎨 Generated Image",
                description=f"**Prompt:** {prompt}",
                color=discord.Color.green()
            )
            embed.set_image(url=image_url)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            await interaction.followup.send(
                f"❌ Failed to generate image: {str(e)}"
            )

    @discordClient.tree.command(name="switchpersona", description="Switch AI personality")
    async def switchpersona(interaction: discord.Interaction, persona: str):
        user_id = str(interaction.user.id)
        
        try:
            available_personas = personas.get_available_personas(user_id)
            
            if persona not in available_personas:
                await interaction.response.send_message(
                    f"❌ Invalid persona. Available personas: {', '.join(available_personas)}",
                    ephemeral=True
                )
                return
            
            # Check permissions for jailbreak personas
            if personas.is_jailbreak_persona(persona):
                try:
                    personas.get_persona_prompt(persona, user_id)
                except PermissionError:
                    await interaction.response.send_message(
                        f"❌ You don't have permission to use the '{persona}' persona. "
                        f"This persona is restricted to administrators only.",
                        ephemeral=True
                    )
                    return
                
                # Warn about jailbreak usage
                await interaction.response.send_message(
                    f"⚠️ **WARNING**: The '{persona}' persona is designed to bypass safety measures. "
                    f"Use at your own risk and responsibility. This action has been logged.",
                    ephemeral=False
                )
                logger.warning(f"User {user_id} activated jailbreak persona: {persona}")
            else:
                await interaction.response.defer(ephemeral=False)
            
            await discordClient.switch_persona(persona, user_id)
            
            message = f"🎭 Switched to **{persona}** persona"
            if personas.is_jailbreak_persona(persona):
                message += " (Jailbreak Mode Active - Admin Only)"
            
            if hasattr(interaction, 'followup'):
                await interaction.followup.send(message)
            else:
                await interaction.channel.send(message)
                
        except Exception as e:
            logger.error(f"Error switching persona: {e}")
            await interaction.response.send_message(
                f"❌ Failed to switch persona: {str(e)}",
                ephemeral=True
            )

    @discordClient.tree.command(name="private", description="Toggle private access")
    async def private(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        if not discordClient.isPrivate:
            discordClient.isPrivate = not discordClient.isPrivate
            logger.warning("\x1b[31mSwitch to private mode\x1b[0m")
            await interaction.followup.send(
                "> **INFO: Next, the response will be sent as ephemeral message and only visible to you.**")
        else:
            discordClient.isPrivate = not discordClient.isPrivate
            logger.info("Switch to public mode")
            await interaction.followup.send(
                "> **INFO: Next, the response will be sent as normal message and visible to everyone.**")

        discordClient.reset_conversation_history()
        await interaction.response.send_message(
            "🔄 Conversation history has been cleared. Starting fresh!",
            ephemeral=False
        )

    @discordClient.tree.command(name="join", description="Join your voice channel")
    async def join(interaction: discord.Interaction):
        """Join the user's current voice channel"""
        # Check if voice is enabled
        if not discordClient.voice_manager.enabled:
            await interaction.response.send_message(
                "❌ Voice features are currently disabled. Set VOICE_ENABLED=True in .env to enable.",
                ephemeral=True
            )
            return
        
        # Check if user is in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "❌ You need to be in a voice channel first!",
                ephemeral=True
            )
            return
        
        # Check if already connected
        if discordClient.voice_manager.is_connected(interaction.guild.id):
            await interaction.response.send_message(
                "⚠️ Already connected to a voice channel in this server!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Join the channel
        success = await discordClient.voice_manager.join_voice_channel(interaction.user.voice.channel)
        
        if success:
            await interaction.followup.send(
                f"✅ Joined {interaction.user.voice.channel.name}! I'm now listening for voice input."
            )
        else:
            await interaction.followup.send(
                "❌ Failed to join voice channel. Check logs for details."
            )
    
    @discordClient.tree.command(name="leave", description="Leave the voice channel")
    async def leave(interaction: discord.Interaction):
        """Leave the current voice channel"""
        if not discordClient.voice_manager.is_connected(interaction.guild.id):
            await interaction.response.send_message(
                "❌ Not connected to any voice channel!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        success = await discordClient.voice_manager.leave_voice_channel(interaction.guild.id)
        
        if success:
            await interaction.followup.send("👋 Left the voice channel!")
        else:
            await interaction.followup.send("❌ Failed to leave voice channel.")
    
    @discordClient.tree.command(name="voicestatus", description="Show voice connection status")
    async def voicestatus(interaction: discord.Interaction):
        """Show the current voice status"""
        status = discordClient.voice_manager.get_status(interaction.guild.id)
        
        embed = discord.Embed(
            title="🎙️ Voice Status",
            color=discord.Color.green() if status["connected"] else discord.Color.red()
        )
        
        embed.add_field(name="Enabled", value="✅ Yes" if status["enabled"] else "❌ No", inline=True)
        embed.add_field(name="Auto Join", value="✅ Yes" if status["auto_join"] else "❌ No", inline=True)
        embed.add_field(name="Connected", value="✅ Yes" if status["connected"] else "❌ No", inline=True)
        
        if status["connected"]:
            embed.add_field(name="Channel", value=status["channel"], inline=False)
            embed.add_field(name="Recording", value="✅ Yes" if status["recording"] else "❌ No", inline=True)
            embed.add_field(name="Playing", value="🔊 Yes" if status["playing"] else "❌ No", inline=True)
            embed.add_field(name="Listening", value="👂 Yes" if status.get("listening", True) else "🔇 No (speaking)", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    @discordClient.tree.command(name="togglevoice", description="Toggle voice features on/off")
    async def togglevoice(interaction: discord.Interaction):
        """Toggle voice features"""
        discordClient.voice_manager.enabled = not discordClient.voice_manager.enabled
        
        status = "enabled" if discordClient.voice_manager.enabled else "disabled"
        emoji = "✅" if discordClient.voice_manager.enabled else "❌"
        
        await interaction.response.send_message(
            f"{emoji} Voice features are now **{status}**!",
            ephemeral=False
        )

    @discordClient.tree.command(name="setreasoning", description="Configure AI reasoning effort level for this channel")
    @app_commands.describe(level="Reasoning effort level (default = let OpenAI decide)")
    @app_commands.choices(level=[
        app_commands.Choice(name="Default (OpenAI decides)", value="default"),
        app_commands.Choice(name="None", value="none"),
        app_commands.Choice(name="Minimal", value="minimal"),
        app_commands.Choice(name="Low", value="low"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="High", value="high"),
    ])
    async def setreasoning(
        interaction: discord.Interaction, 
        level: app_commands.Choice[str]
    ):
        """Set the reasoning level for GPT-5.1 in this channel"""
        level_value = level.value if isinstance(level, app_commands.Choice) else level
        channel_id = str(interaction.channel_id)
        
        # Handle "default" to unset the reasoning level
        if level_value.lower() == "default":
            success = reasoning_config.remove_reasoning_level(channel_id)
            if success:
                await interaction.response.send_message(
                    "✅ Reasoning level reset to **default** (OpenAI will decide). "
                    "The AI will use its default reasoning effort for this channel.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    "❌ Failed to reset reasoning level. Please try again.",
                    ephemeral=True
                )
            return
        
        # Validate and set the reasoning level
        if level_value.lower() not in reasoning_config.VALID_LEVELS:
            await interaction.response.send_message(
                f"❌ Invalid reasoning level. Valid options: {', '.join(reasoning_config.VALID_LEVELS)}, or 'default' to unset.",
                ephemeral=True
            )
            return
        
        success = reasoning_config.set_reasoning_level(channel_id, level_value.lower())
        
        if success:
            await interaction.response.send_message(
                f"✅ Reasoning level set to **{level_value.lower()}** for this channel. "
                f"The AI will use this reasoning effort when responding here.",
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to set reasoning level. Please try again.",
                ephemeral=True
            )

    @discordClient.tree.command(name="getreasoning", description="Check current reasoning level for this channel")
    async def getreasoning(interaction: discord.Interaction):
        """Get the current reasoning level setting for this channel"""
        channel_id = str(interaction.channel_id)
        current_level = reasoning_config.get_reasoning_level(channel_id)
        
        if current_level:
            await interaction.response.send_message(
                f"🧠 Current reasoning level: **{current_level}**\n"
                f"Valid levels: {', '.join(reasoning_config.VALID_LEVELS)}, or 'default' to unset",
                ephemeral=False
            )
        else:
            await interaction.response.send_message(
                f"🧠 Current reasoning level: **default** (OpenAI decides)\n"
                f"Valid levels: {', '.join(reasoning_config.VALID_LEVELS)}, or 'default' to unset",
                ephemeral=False
            )

    @discordClient.tree.command(name="help", description="Show all available commands")
    async def help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 AI Discord Bot - Help",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        commands = [
            ("💬 **Chat Commands**", [
            ]),
            ("📬 **Queue Management**", [
                ("/enqueue", "Enter queue mode to build longer messages"),
                ("/send", "Send all queued messages as one payload"),
                ("/viewqueue", "View your current message queue"),
                ("/clearqueue", "Clear queue and exit queue mode")
            ]),
            ("🎨 **Image Generation**", [
                ("/draw [prompt]", "Generate an image from text")
            ]),
            ("🎙️ **Voice Commands**", [
                ("/join", "Join your current voice channel"),
                ("/leave", "Leave the voice channel"),
                ("/voicestatus", "Show voice connection status"),
                ("/togglevoice", "Toggle voice features on/off")
            ]),
            ("🎭 **Personas**", [
                ("/switchpersona [name]", "Change AI personality"),
                ("Available", "standard, creative, technical, casual"),
                ("Admin Only", "jailbreak-v1, jailbreak-v2, jailbreak-v3 (restricted)")
            ]),
            ("⚙️ **Settings**", [
                ("/help", "Show this help message"),
                ("/setreasoning [level]", "Set AI reasoning effort (none/minimal/low/medium/high/default)"),
                ("/getreasoning", "Check current reasoning level for this channel")
            ])
        ]
        
        for category, cmds in commands:
            value = "\n".join([f"`{cmd}` - {desc}" for cmd, desc in cmds])
            embed.add_field(name=category, value=value, inline=False)
        
        # Add provider info
        info = discordClient.get_current_provider_info()
        embed.add_field(
            name="📊 Current Settings",
            value=f"**Provider:** {info['provider']}\n**Model:** {info['current_model']}",
            inline=False
        )
        
        # Add voice status
        voice_status = discordClient.voice_manager.get_status(interaction.guild.id)
        voice_info = f"**Enabled:** {'Yes' if voice_status['enabled'] else 'No'}\n"
        voice_info += f"**Connected:** {'Yes' if voice_status['connected'] else 'No'}"
        embed.add_field(
            name="🎙️ Voice Status",
            value=voice_info,
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @discordClient.tree.command(name="enqueue", description="Enter queue mode to build longer messages")
    async def enqueue(interaction: discord.Interaction):
        """Activate queue mode for building longer messages"""
        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel_id)
        
        # Check if already in queue mode
        if discordClient.is_queue_mode(user_id, channel_id):
            await interaction.response.send_message(
                "⚠️ Queue mode is already active! Your messages are being queued.\n"
                "Use `/viewqueue` to see your queue, `/send` to send, or `/clearqueue` to cancel.",
                ephemeral=False
            )
            return
        
        # Enable queue mode
        discordClient.enable_queue_mode(user_id, channel_id)
        
        await interaction.response.send_message(
            "📝 **Queue mode activated!**\n\n"
            "Your next messages in this channel will be queued instead of sent immediately.\n"
            "• Use `/send` to send all queued messages as one payload\n"
            "• Use `/viewqueue` to see your current queue\n"
            "• Use `/clearqueue` to cancel and clear the queue",
            ephemeral=False
        )

    @discordClient.tree.command(name="send", description="Send all queued messages as one payload")
    async def send(interaction: discord.Interaction):
        """Send all queued messages concatenated together"""
        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel_id)
        
        # Check if in queue mode
        if not discordClient.is_queue_mode(user_id, channel_id):
            await interaction.response.send_message(
                "❌ Queue mode is not active. Use `/enqueue` to start queueing messages.",
                ephemeral=True
            )
            return
        
        # Get queued messages
        queue = discordClient.get_queue(user_id, channel_id)
        
        if not queue:
            await interaction.response.send_message(
                "❌ No messages in queue. Send some messages first, or use `/clearqueue` to exit queue mode.",
                ephemeral=True
            )
            return
        
        # Concatenate messages
        concatenated_message = "\n\n".join(queue)
        
        # Clear queue and disable queue mode
        discordClient.clear_queue(user_id, channel_id)
        discordClient.disable_queue_mode(user_id, channel_id)
        
        # Send through normal message flow
        await discordClient.enqueue_message(interaction, concatenated_message)

    @discordClient.tree.command(name="viewqueue", description="View your current message queue")
    async def viewqueue(interaction: discord.Interaction):
        """Display the current message queue"""
        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel_id)
        
        # Get queue status
        is_active = discordClient.is_queue_mode(user_id, channel_id)
        queue = discordClient.get_queue(user_id, channel_id)
        
        if not queue:
            status_msg = "🔴 Queue mode: inactive" if not is_active else "🟢 Queue mode: active"
            await interaction.response.send_message(
                f"{status_msg}\n\n"
                "📭 Your queue is empty.\n"
                "Use `/enqueue` to start queueing messages.",
                ephemeral=False
            )
            return
        
        # Calculate total character count
        total_chars = sum(len(msg) for msg in queue)
        
        # Build queue display
        embed = discord.Embed(
            title="📬 Message Queue",
            description=f"**Status:** {'🟢 Active' if is_active else '🔴 Inactive'}\n"
                       f"**Messages:** {len(queue)}\n"
                       f"**Total Characters:** {total_chars:,}",
            color=discord.Color.blue()
        )
        
        # Show each message (truncate if too long)
        for i, msg in enumerate(queue, 1):
            # Truncate message if longer than 200 chars for display
            display_msg = msg if len(msg) <= 200 else f"{msg[:200]}..."
            embed.add_field(
                name=f"Message {i}",
                value=f"```{display_msg}```",
                inline=False
            )
            
            # Discord embed limit is 25 fields
            if i >= 25:
                embed.add_field(
                    name="...",
                    value=f"_and {len(queue) - 25} more message(s)_",
                    inline=False
                )
                break
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @discordClient.tree.command(name="clearqueue", description="Clear your message queue and exit queue mode")
    async def clearqueue(interaction: discord.Interaction):
        """Clear the message queue and disable queue mode"""
        user_id = str(interaction.user.id)
        channel_id = str(interaction.channel_id)
        
        # Get current queue size before clearing
        queue_size = discordClient.get_queue_size(user_id, channel_id)
        is_active = discordClient.is_queue_mode(user_id, channel_id)
        
        if queue_size == 0 and not is_active:
            await interaction.response.send_message(
                "ℹ️ No active queue to clear.",
                ephemeral=True
            )
            return
        
        # Clear queue and disable queue mode
        discordClient.clear_queue(user_id, channel_id)
        discordClient.disable_queue_mode(user_id, channel_id)
        
        await interaction.response.send_message(
            f"🗑️ Queue cleared! Removed {queue_size} message{'s' if queue_size != 1 else ''} and exited queue mode.",
            ephemeral=False
        )

    # Handle regular messages when replyall is on
    @discordClient.event
    async def on_message(message):
        if discordClient.is_replying_all:
            if message.author == discordClient.user:
                return
            
            if discordClient.replying_all_discord_channel_id:
                if message.channel.id != int(discordClient.replying_all_discord_channel_id):
                    return
            
            username = str(message.author)
            user_message = message.content
            discordClient.current_channel = message.channel
            
            logger.info(f"\x1b[31m{username}\x1b[0m : {user_message} in ({message.channel})")
            
            # Check if user is in queue mode
            user_id = str(message.author.id)
            channel_id = str(message.channel.id)
            if discordClient.is_queue_mode(user_id, channel_id):
                # Add to queue instead of processing immediately
                discordClient.add_to_queue(user_id, channel_id, user_message)
                return
            
            await discordClient.enqueue_message(message, user_message)

    # Run the bot
    discordClient.run(os.getenv("DISCORD_BOT_TOKEN"))