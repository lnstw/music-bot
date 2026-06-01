import discord
from discord.ext import commands
import asyncio
import logging
import datetime
import os
from discord.ext import tasks
import lava_lyra

from core.view import RefreshButton, opselect_view, CategorySelectView, CommandSelectView, CommandDetailView
from core.embed import EMBED_COLORS
from core.player import CustomPlayer
from core.config import config
from core.log import setup_logging

setup_logging()
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.all()
intents.message_content = True

class MusicClient(commands.Bot):
    def __init__(self, config_dict: dict):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config_dict
        self.last_activity = {}
        self.auto_update_tasks: dict[str, asyncio.Task] = {}
        self.lavalink_heartbeats: dict[int, float] = {}
        self.status_index = 0
        self.empty_channel_timers: dict[int, dict] = {}
        self.queues: dict[int, list] = {}
        self.last_channels: dict[int, int] = {}

    @tasks.loop(minutes=1)
    async def check_inactive_guilds(self):
        current_time = datetime.datetime.now()
        inactive_timeout = datetime.timedelta(minutes=5)
        for guild_id in list(self.last_activity.keys()):
            guild = self.get_guild(guild_id)
            if not guild or not isinstance(guild.voice_client, CustomPlayer):
                continue

            if guild.voice_client.is_playing:
                continue

            player: CustomPlayer = guild.voice_client

            last_time = self.last_activity.get(guild_id)
            if last_time and (current_time - last_time) > inactive_timeout:
                if player.queue:
                    player.queue.clear()
                if guild_id in self.last_activity:
                    del self.last_activity[guild_id]
                logging.info(f"已重置閒置伺服器 (ID: {guild_id}) 的播放清單和當前歌曲")
        self.status_index = 0

    def generate_status_list(self) -> list[str]:
        guild_count = len(self.guilds)
        user_count = sum(g.member_count or 0 for g in self.guilds)
        playing_count = sum(
            1 for guild in self.guilds
            if guild.voice_client and isinstance(guild.voice_client, CustomPlayer) and guild.voice_client.is_playing
        )
        return [
            "使用 /help 查看幫助",
            f"正在偷窺 {guild_count} 個伺服器",
            f"正在監視 {user_count} 個人",
            f"正在播放音樂於 {playing_count} 個伺服器"
        ]

    @tasks.loop(seconds=10)
    async def auto_update_status(self):
        try:
            status_list = self.generate_status_list()
            subtitle = status_list[self.status_index]
            self.status_index = (self.status_index + 1) % len(status_list)

            for guild in self.guilds:
                if guild.voice_client and isinstance(guild.voice_client, CustomPlayer):
                    if not guild.voice_client.is_playing:
                        continue
                    track = guild.voice_client.current
                    if track:
                        await self.update_presence(current_song=track.title, subtitle=subtitle)
                        return

            await self.update_presence(subtitle=subtitle)
        except Exception as e:
            logging.error(f"更新狀態時發生錯誤：{e}")

    async def update_presence(self,current_song: str = None, subtitle: str = None):
        if current_song:
            name = f"{current_song} | {subtitle}"
            activity_type = discord.ActivityType.listening
        else:
            name = f"{subtitle}"
            activity_type = discord.ActivityType.streaming

        activity = discord.Activity(type=activity_type, name=name)
        await self.change_presence(status=discord.Status.dnd, activity=activity)

    async def start_empty_channel_timer(self, channel: discord.abc.GuildChannel | discord.VoiceChannel):
        channel_id = channel.id
        guild_id = channel.guild.id
        if channel_id in self.empty_channel_timers:
            return
        self.empty_channel_timers[channel_id] = {
            'start_time': datetime.datetime.now(),
            'warned': False
        }

        async def _worker():
            try:
                await asyncio.sleep(45)
                cur_channel = self.get_channel(channel_id)
                if not cur_channel:
                    self.empty_channel_timers.pop(channel_id, None)
                    return

                if (channel_id in self.empty_channel_timers and
                    len(cur_channel.members) == 1 and
                    self.user in cur_channel.members):
                    if not self.empty_channel_timers[channel_id]['warned']:
                        warn_embed = discord.Embed(
                            title="⚠️ 即將自動離開",
                            description=f"頻道內只剩機器人\n將在 15 秒後自動離開",
                            color=EMBED_COLORS['warning']
                        )
                        await send_message_to_last_channel(guild_id=guild_id, embed=warn_embed)
                        self.empty_channel_timers[channel_id]['warned'] = True
                    await asyncio.sleep(15)

                    cur_channel = self.get_channel(channel_id)
                    if (channel_id in self.empty_channel_timers and
                        cur_channel and
                        len(cur_channel.members) == 1 and
                        self.user in cur_channel.members):
                        vc = cur_channel.guild.voice_client
                        if vc:
                            await vc.disconnect()
                            bye_embed = discord.Embed(
                                title="👋 掰",
                                description=f"",
                                color=EMBED_COLORS['success']
                            )
                            await send_message_to_last_channel(guild_id=guild_id, embed=bye_embed)
                            if guild_id in self.queues:
                                self.queues[guild_id].clear()
                            await self.update_presence()
            finally:
                self.empty_channel_timers.pop(channel_id, None)
                task_key = f"empty_{channel_id}"
                task = self.auto_update_tasks.pop(task_key, None)
                if task:
                    try:
                        task.cancel()
                    except Exception:
                        pass

        task = asyncio.create_task(_worker())
        self.auto_update_tasks[f"empty_{channel_id}"] = task

    def cancel_empty_channel_timer(self, channel_id: int):
        if channel_id in self.empty_channel_timers:
            self.empty_channel_timers.pop(channel_id, None)
        task_key = f"empty_{channel_id}"
        task = self.auto_update_tasks.pop(task_key, None)
        if task:
            try:
                task.cancel()
            except Exception:
                pass

    async def setup_hook(self):
        await self.tree.sync()
        logging.info("命令已同步！")
    
    async def _connect_lavalink(self):
        try:
            host = self.config.get("node_host", "").strip('"')
            port = int(self.config.get("node_port", 443))
            ssl_config = str(self.config.get("node_ssl", "0")).strip('"').strip()
            secure = ssl_config in ("1", "true", "True", "TRUE")
            password = self.config.get("node_pw", "").strip('"')
            try:
                node = await asyncio.wait_for(
                    lava_lyra.NodePool.create_node(
                        bot=self,
                        host=host,
                        port=port,
                        identifier="main",
                        secure=secure,
                        password=password,
                        lyrics=True,
                        search=True,
                        fallback=True
                    ),
                    timeout=30
                )
                logging.info('Lavalink節點已連接成功！')
                self._lavalink_connected = True
            except asyncio.TimeoutError:
                logging.error('連接超時 - Lavalink伺服器可能無法訪問')
        except Exception as e:
            logging.error(f'Lavalink連接失敗：{e}', exc_info=True)

    async def on_ready(self):
        logging.info(f'已登入為 {self.user}')
        self.add_view(RefreshButton())
        self.add_view(opselect_view(self))
        self.add_view(CategorySelectView())
        self.add_view(CommandSelectView({}, {}, ""))
        self.add_view(CommandDetailView())

        if not self.auto_update_status.is_running():
            self.auto_update_status.start() 
        if not self.check_inactive_guilds.is_running():
            self.check_inactive_guilds.start()
        if not hasattr(self, '_lavalink_connected'):
            self._lavalink_connected = False
            asyncio.create_task(self._connect_lavalink())

bot = MusicClient(config)

def resolve_extension_name(ext: str) -> str:
    if ext.startswith("cogs."):
        ext = ext[5:]
    for cog_name, cog_instance in bot.cogs.items():
        if ext.lower() == cog_name.lower():
            module = cog_instance.__module__
            if module.startswith("cogs."):
                return module[5:]
    return ext

async def send_message_to_last_channel(guild_id: int, message: str = None, embed: discord.Embed = None):
    if guild_id in bot.last_channels:
        guild = bot.get_guild(guild_id)
        if guild:
            channel = guild.get_channel(bot.last_channels[guild_id])
            if channel:
                try:
                    if embed:
                        await channel.send(embed=embed)
                    elif message:
                        await channel.send(message)
                except Exception as e:
                    logging.error(f"發送訊息時發生錯誤: {e}")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        if interaction.guild and interaction.channel_id:
            bot.last_channels[interaction.guild.id] = interaction.channel_id
    except Exception:
        pass

@bot.event
async def on_message(message: discord.Message):
    try:
        if message.guild and not message.author.bot:
            bot.last_channels[message.guild.id] = message.channel.id
    except Exception:
        pass
    await bot.process_commands(message)

@bot.tree.command(name="load", description="載入 Cog 模組")
@commands.is_owner()
async def load(interaction: discord.Interaction, extension: str):
    ext = resolve_extension_name(extension)
    try:
        await bot.load_extension(f"cogs.{ext}")
        await bot.tree.sync()
        await interaction.response.send_message(f"已載入 `{extension}` (模組: {ext})", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"載入失敗: {e}", ephemeral=True)

@bot.tree.command(name="unload", description="卸載 Cog 模組")
@commands.is_owner()
async def unload(interaction: discord.Interaction, extension: str):
    ext = resolve_extension_name(extension)
    try:
        await bot.unload_extension(f"cogs.{ext}")
        await bot.tree.sync()
        await interaction.response.send_message(f"已卸載 `{extension}` (模組: {ext})", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"卸載失敗: {e}", ephemeral=True)

@bot.tree.command(name="reload", description="重新載入 Cog 模組")
@commands.is_owner()
async def reload(interaction: discord.Interaction, extension: str):
    ext = resolve_extension_name(extension)
    try:
        await bot.reload_extension(f"cogs.{ext}")
        await interaction.response.send_message(f"已重新載入 `{extension}` (模組: {ext})", ephemeral=True)
        await bot.tree.sync()
    except Exception as e:
        await interaction.response.send_message(f"重新載入失敗: {e}", ephemeral=True)

@bot.tree.command(name="list_cogs", description="查看已載入的 Cogs")
@commands.is_owner()
async def list_cogs(interaction: discord.Interaction):
    loaded_exts = list(bot.extensions.keys())
    if not loaded_exts:
        await interaction.response.send_message("目前沒有載入任何 Cog。", ephemeral=True)
        return
    
    formatted_list = []
    for ext in loaded_exts:
        classes = [name for name, cog in bot.cogs.items() if cog.__module__ == ext]
        class_str = f" (類別: {', '.join(classes)})" if classes else ""
        formatted_list.append(f"- `{ext}`{class_str}")
        
    embed = discord.Embed(
        title="🧩 已載入的 Cogs 模組",
        description="\n".join(formatted_list),
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="開發者命令", description="開發者命令")
@commands.is_owner()
async def 開發者命令(interaction: discord.Interaction):
    if interaction.user.id != int(config.get("discord_user_id")):
        await interaction.response.send_message("❌ 你沒有權限使用此指令", ephemeral=True)
        return
    view = opselect_view(bot)
    await interaction.response.send_message("請選擇功能", view=view, ephemeral=True)


async def load_all_extensions():
    for root, _dirs, files in os.walk("./cogs"):
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                module_path = os.path.join(root, filename)[2:-3].replace(os.sep, ".")
                try:
                    await bot.load_extension(module_path)
                    logging.info(f"已載入 Cog: {module_path}")
                except commands.NoEntryPointError:
                    logging.warning(f"已略過非 Cog 模組: {module_path}")
                except Exception as e:
                    logging.error(f"載入 Cog 時發生錯誤: {module_path} - {e}")

@bot.listen()
async def on_lyra_track_end(player: CustomPlayer, track: lava_lyra.Track, reason: str):
    await player.play_next()

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel is None or after.channel == before.channel:
        return
    if before.channel and bot.user in before.channel.members:
        channel = before.channel
        if len(channel.members) == 1:
            await bot.start_empty_channel_timer(channel)
        else:
            bot.cancel_empty_channel_timer(channel.id)

async def main():
    token = os.getenv("discord_bot_token")
    if token is None:
        raise RuntimeError("缺少環境變數 discord_bot_token")
    await load_all_extensions()
    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("正在關閉機器人...")