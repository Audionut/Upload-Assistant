# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import datetime
import logging
from pathlib import Path
from src.console import console
import discord
from discord.ext import commands


async def run(config):
    """
    Starts the bot. If you want to create a database connection pool or other session for the bot to use,
    create it here and pass it to the bot as a kwarg.
    """
    intents = discord.Intents.default()
    intents.message_content = True

    bot = Bot(
        config=config,
        description=config['DISCORD']['discord_bot_description'],
        intents=intents
    )

    try:
        await bot.start(config['DISCORD']['discord_bot_token'])
    except KeyboardInterrupt:
        await bot.close()


class Bot(commands.Bot):
    def __init__(self, *, config, description, intents):
        super().__init__(
            command_prefix=self.get_prefix_,
            description=description,
            intents=intents
        )
        self.start_time = None
        self.app_info = None
        self.config = config

    async def setup_hook(self):
        # Called before the bot connects to Discord
        asyncio.create_task(self.track_start())
        await self.load_all_extensions()

    async def track_start(self):
        """
        Waits for the bot to connect to discord and then records the time.
        Can be used to work out uptime.
        """
        await self.wait_until_ready()
        self.start_time = datetime.datetime.utcnow()

    async def get_prefix_(self, bot, message):
        """
        A coroutine that returns a prefix.
        """
        prefix = [self.config['DISCORD']['command_prefix']]
        return commands.when_mentioned_or(*prefix)(bot, message)

    async def load_all_extensions(self):
        """
        Attempts to load all .py files in /cogs/ as cog extensions
        """
        await self.wait_until_ready()
        await asyncio.sleep(1)  # ensure that on_ready has completed and finished printing
        cogs = [x.stem for x in Path('cogs').glob('*.py')]
        for extension in cogs:
            try:
                await self.load_extension(f'cogs.{extension}')
                print(f'loaded {extension}')
            except Exception as e:
                error = f'{extension}\n {type(e).__name__} : {e}'
                print(f'failed to load extension {error}')
            print('-' * 10)

    async def on_ready(self):
        """
        This event is called every time the bot connects or resumes connection.
        """
        print('-' * 10)
        self.app_info = await self.application_info()
        print(f'Logged in as: {self.user.name}\n'
              f'Using discord.py version: {discord.__version__}\n'
              f'Owner: {self.app_info.owner}\n')
        print('-' * 10)
        channel = self.get_channel(int(self.config['DISCORD']['discord_channel_id']))
        if channel:
            await channel.send(f'{self.user.name} is now online')

    async def on_message(self, message):
        """
        This event triggers on every message received by the bot. Including one's that it sent itself.
        """
        if message.author.bot:
            return  # ignore all bots
        await self.process_commands(message)


async def send_discord_notification(config, bot, message, debug=False, meta=None):
    """
    Send a notification message to Discord channel.

    Args:
        bot: Discord bot instance (can be None)
        message: Message string to send
        meta: Optional meta dict for debug logging

    Returns:
        bool: True if message was sent successfully, False otherwise
    """
    only_unattended = config.get('DISCORD', {}).get('only_unattended', False)
    if only_unattended and meta and not meta.get('unattended', False):
        return False
    if not bot or not hasattr(bot, 'is_ready') or not bot.is_ready():
        if debug:
            console.print("[yellow]Discord bot not ready - skipping notifications")
        return False

    try:
        channel_id = int(config['DISCORD']['discord_channel_id'])
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
            if debug:
                console.print(f"[green]Discord notification sent: {message}")
            return True
        else:
            console.print("[yellow]Discord channel not found")
            return False
    except Exception as e:
        console.print(f"[yellow]Discord notification error: {e}")
        return False


async def send_upload_status_notification(config, bot, meta):
    """Send Discord notification with upload status including failed trackers."""
    only_unattended = config.get('DISCORD', {}).get('only_unattended', False)
    if only_unattended and meta and not meta.get('unattended', False):
        return False
    if not bot or not hasattr(bot, 'is_ready') or not bot.is_ready():
        return False

    tracker_status = meta.get('tracker_status', {})
    if not tracker_status:
        return False

    # Get list of trackers where upload is True
    successful_uploads = [
        tracker for tracker, status in tracker_status.items()
        if status.get('upload', False)
    ]

    # Get list of failed trackers with reasons
    failed_trackers = []
    for tracker, status in tracker_status.items():
        if not status.get('upload', False):
            if status.get('banned', False):
                failed_trackers.append(f"{tracker} (banned)")
            elif status.get('skipped', False):
                failed_trackers.append(f"{tracker} (skipped)")
            elif status.get('dupe', False):
                failed_trackers.append(f"{tracker} (dupe)")

    release_name = meta.get('name', meta.get('title', 'Unknown Release'))
    message_parts = []

    if successful_uploads:
        message_parts.append(f"✅ **Uploaded to:** {', '.join(successful_uploads)} - {release_name}")

    if failed_trackers:
        message_parts.append(f"❌ **Failed:** {', '.join(failed_trackers)}")

    if not message_parts:
        return False

    message = "\n".join(message_parts)

    try:
        channel_id = int(config['DISCORD']['discord_channel_id'])
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
            return True
    except Exception as e:
        console.print(f"[yellow]Discord notification error: {e}")

    return False


if __name__ == '__main__':
    # Only used when running discordbot.py directly
    from data.config import config
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(config))
