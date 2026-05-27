import os
from dotenv import load_dotenv

CONFIG_PATH = ".env"
CONFIG_KEYS = [
    "discord_user_name",
    "discord_user_id",
    "discord_guild_id",
    "discord_voice_channel_id",
    "spotify_client_id",
    "spotify_client_secret",
    "node_url",
    "node_pw",
    "discord_bot_token"
]
CONFIG_TEMPLATE = """# 請填寫以下值，注意不要公開此檔案
discord_user_name=請填入你的discord名稱
discord_user_id=請填入你的discord_id
discord_guild_id=請填入你的伺服器ID(建議是單獨機器人的群組,機器人掛著使用)
discord_voice_channel_id=請填入你的語音頻道ID(機器人掛著使用)
spotify_client_id=請填入你的client_id
spotify_client_secret=請填入你的client_secret
node_url=請填入你的lavalink網址
node_pw=請填入你的lavalink密碼
discord_bot_token=請填入你的discord token
"""

def check_and_create_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        print("已自動建立 .env，請填入相關資訊後重新啟動程式。")
        exit(0)

    load_dotenv(CONFIG_PATH)

    config = {}
    missing = []
    for k in CONFIG_KEYS:
        v = os.getenv(k)
        if v is None:
            missing.append(k)
        else:
            config[k] = v

    if missing:
        with open(CONFIG_PATH, "a", encoding="utf-8") as f:
            for k in missing:
                f.write(f"{k}=請填入你的資料\n")
        print(f".env 缺少欄位，已自動補上：{', '.join(missing)}，請補齊後重新啟動。")
        exit(0)

    for k in CONFIG_KEYS:
        if config[k].startswith("請填入"):
            print(f"請在 .env 裡填入 {k} 的正確值後再啟動。")
            exit(0)

    return config

config = check_and_create_config()

import discord
from discord.ext import commands
import asyncio, os
import logging
from dotenv import load_dotenv
import wavelink
import spotipy
import datetime
from datetime import timedelta
from spotipy.oauth2 import SpotifyClientCredentials
from discord.ext import tasks
from discord import app_commands

from service.view import RefreshButton, opselect_view, CategorySelectView, CommandSelectView, CommandDetailView
from service.channel import send_message_to_last_channel
from service.play import play_next
from service.embed import create_error_embed, EMBED_COLORS


logging.basicConfig(level=logging.INFO)
intents = discord.Intents.all()
intents.message_content = True

@tasks.loop(minutes=1)
async def check_inactive_guilds():
    current_time = datetime.datetime.now()
    inactive_timeout = datetime.timedelta(minutes=5)
    for guild_id in list(client.last_activity.keys()):
        guild = client.get_guild(guild_id)
        if guild and guild.voice_client and guild.voice_client.playing:
            continue     
        last_time = client.last_activity.get(guild_id)
        if last_time and (current_time - last_time) > inactive_timeout:
            if guild_id in client.queues:
                client.queues[guild_id].clear()
            if guild_id in client.current_songs:
                del client.current_songs[guild_id]
            if guild_id in client.force_stop:
                client.force_stop[guild_id] = False
            if guild_id in client.show_now_song:
                client.show_now_song[guild_id] = True
            if guild_id in client.empty_channel_timers:
                del client.empty_channel_timers[guild_id]
            if guild_id in client.guild_volumes:
                del client.guild_volumes[guild_id]
            if guild_id in client.last_activity:
                del client.last_activity[guild_id]
            print(f"已重置閒置伺服器 (ID: {guild_id}) 的播放清單和當前歌曲")

class MusicClient(commands.Bot):
    def __init__(self, config_dict: dict):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config_dict
        self.queues = {}
        self.current_songs = {}
        self.last_channels = {}
        self.loop_mode = {}
        self.auto_recommend = {}
        self.force_stop = {}
        self.show_now_song = {}
        self.empty_channel_timers = {}
        self.last_activity = {}
        self.guild_volumes = {}
        self.default_volume = 10
        self.status_index = 0
        self.auto_update_tasks: dict[int, asyncio.Task] = {}
        self.spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=self.config["spotify_client_id"],
            client_secret=self.config["spotify_client_secret"],
        ))
        self.lavalink_heartbeats: dict[int, float] = {}
    def generate_status_list(self) -> list[str]:
        guild_count = len(self.guilds)
        user_count = sum(g.member_count or 0 for g in self.guilds)
        playing_count = sum(
            1 for guild in self.guilds
            if guild.voice_client and guild.voice_client.playing
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
                if guild.voice_client and guild.voice_client.playing:
                    song = self.current_songs.get(guild.id)
                    if song:
                        await self.update_presence(current_song=song.title, subtitle=subtitle)
                        return

            await self.update_presence(subtitle=subtitle)
        except Exception as e:
            print(f"更新狀態時發生錯誤：{e}")

    async def update_presence(self,current_song: str = None, subtitle: str = None):
        if current_song:
            name = f"{current_song} | {subtitle}"
            activity_type = discord.ActivityType.listening
        else:
            name = f"{subtitle}"
            activity_type = discord.ActivityType.streaming

        activity = discord.Activity(type=activity_type, name=name)
        await self.change_presence(status=discord.Status.dnd, activity=activity)

    async def setup_hook(self):
        try:
            node: wavelink.Node = wavelink.Node(
                uri=self.config["node_url"],
                password=self.config["node_pw"],
            )
            await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)
            logging.info('音樂節點連接成功！')
            await self.tree.sync()
            logging.info("命令已同步！")
        except Exception as e:
            print(f'音樂節點連接失敗：{e}')

    async def on_ready(self):
        logging.info(f'已登入為 {self.user}')
        logging.info("Done!")
        self.add_view(RefreshButton())
        self.add_view(opselect_view())
        self.add_view(CategorySelectView())
        self.add_view(CommandSelectView({}, {}, ""))
        self.add_view(CommandDetailView())

        if not self.auto_update_status.is_running():
            self.auto_update_status.start() 
        if not check_inactive_guilds.is_running():
            check_inactive_guilds.start()

client = MusicClient(config)
_client = client
from service.embed import set_client_ref
set_client_ref(client)

def resolve_extension_name(ext: str) -> str:
    if ext.startswith("cogs."):
        ext = ext[5:]
    for cog_name, cog_instance in client.cogs.items():
        if ext.lower() == cog_name.lower():
            module = cog_instance.__module__
            if module.startswith("cogs."):
                return module[5:]
    return ext

@client.tree.command(name="load", description="載入 Cog 模組")
@commands.is_owner()
async def load(interaction: discord.Interaction, extension: str):
    ext = resolve_extension_name(extension)
    try:
        await client.load_extension(f"cogs.{ext}")
        await client.tree.sync()
        await interaction.response.send_message(f"已載入 `{extension}` (模組: {ext})", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"載入失敗: {e}", ephemeral=True)

@client.tree.command(name="unload", description="卸載 Cog 模組")
@commands.is_owner()
async def unload(interaction: discord.Interaction, extension: str):
    ext = resolve_extension_name(extension)
    try:
        await client.unload_extension(f"cogs.{ext}")
        await client.tree.sync()
        await interaction.response.send_message(f"已卸載 `{extension}` (模組: {ext})", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"卸載失敗: {e}", ephemeral=True)

@client.tree.command(name="reload", description="重新載入 Cog 模組")
@commands.is_owner()
async def reload(interaction: discord.Interaction, extension: str):
    ext = resolve_extension_name(extension)
    try:
        await client.reload_extension(f"cogs.{ext}")
        await interaction.response.send_message(f"已重新載入 `{extension}` (模組: {ext})", ephemeral=True)
        await client.tree.sync()
    except Exception as e:
        await interaction.response.send_message(f"重新載入失敗: {e}", ephemeral=True)

@client.tree.command(name="list_cogs", description="查看已載入的 Cogs")
@commands.is_owner()
async def list_cogs(interaction: discord.Interaction):
    loaded_exts = list(client.extensions.keys())
    if not loaded_exts:
        await interaction.response.send_message("目前沒有載入任何 Cog。", ephemeral=True)
        return
    
    formatted_list = []
    for ext in loaded_exts:
        classes = [name for name, cog in client.cogs.items() if cog.__module__ == ext]
        class_str = f" (類別: {', '.join(classes)})" if classes else ""
        formatted_list.append(f"- `{ext}`{class_str}")
        
    embed = discord.Embed(
        title="🧩 已載入的 Cogs 模組",
        description="\n".join(formatted_list),
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="開發者命令", description="開發者命令")
@commands.is_owner()
async def 開發者命令(interaction: discord.Interaction):
    if interaction.user.id != int(config["discord_user_id"]):
        await interaction.response.send_message("❌ 你沒有權限使用此指令", ephemeral=True)
        return
    view = opselect_view()
    await interaction.response.send_message("請選擇功能", view=view, ephemeral=True)


async def load_all_extensions():
    for root, _dirs, files in os.walk("./cogs"):
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                module_path = os.path.join(root, filename)[2:-3].replace(os.sep, ".")
                try:
                    await client.load_extension(module_path)
                    logging.info(f"已載入 Cog: {module_path}")
                except commands.NoEntryPointError:
                    logging.warning(f"已略過非 Cog 模組: {module_path}")
                except Exception as e:
                    logging.error(f"載入 Cog 時發生錯誤: {module_path} - {e}")

@client.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    try:
        if not payload.player or not payload.player.guild:
            return
        guild = payload.player.guild
        guild_id = guild.id
        if (guild_id in client.queues and client.queues[guild_id]) or \
           (guild_id in client.auto_recommend and client.auto_recommend[guild_id]) or \
           (client.loop_mode.get(guild_id, False) and guild_id in client.current_songs):
            await play_next(guild=guild, vc=payload.player, client=client)
        else:
            await client.update_presence()
            embed = discord.Embed(
                title="✅ 播放完成",
                description="播放清單已播放完畢",
                color=EMBED_COLORS['success']
            )
            await send_message_to_last_channel(guild_id=guild_id, embed=embed)
    except Exception as e:
        print(f"處理歌曲結束時發生錯誤：{e}")
        if payload.player and payload.player.guild:
            error_embed = create_error_embed(f"處理歌曲結束時發生錯誤：{str(e)}")
            await send_message_to_last_channel(guild_id=payload.player.guild.id, embed=error_embed)

async def main():
    token = os.getenv("discord_bot_token")
    if token is None:
        raise RuntimeError("缺少環境變數 discord_bot_token")
    await load_all_extensions()
    await client.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("\n正在關閉機器人...")