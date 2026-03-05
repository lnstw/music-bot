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
import wavelink
import spotipy
from discord.ext import tasks
import datetime
from datetime import timedelta
from spotipy.oauth2 import SpotifyClientCredentials
from discord import app_commands
import aiohttp
from io import BytesIO
import requests
from PIL import Image
import colorsys
import asyncio
from typing import Any


class LavalinkPlayerCompat(wavelink.Player):
    """Compatibility layer for Lavalink v4 voice payload requirements."""

    def _ensure_channel_id(self) -> None:
        channel = getattr(self, "channel", None)
        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return

        voice_payload = getattr(self, "_voice_state", None)
        if not isinstance(voice_payload, dict):
            return

        voice_data = voice_payload.setdefault("voice", {})
        voice_data.setdefault("channel_id", str(channel_id))

    async def on_voice_state_update(self, data: Any, /) -> None:
        await super().on_voice_state_update(data)
        self._ensure_channel_id()

    async def on_voice_server_update(self, data: Any) -> None:
        self._ensure_channel_id()
        await super().on_voice_server_update(data)

    async def _dispatch_voice_update(self) -> None:
        assert self.guild is not None
        self._ensure_channel_id()

        data = self._voice_state.get("voice", {})
        session_id = data.get("session_id")
        token = data.get("token")
        endpoint = data.get("endpoint")
        channel_id = data.get("channel_id")

        if not session_id or not token or not endpoint or not channel_id:
            return

        request = {
            "voice": {
                "sessionId": session_id,
                "token": token,
                "endpoint": endpoint,
                "channelId": str(channel_id),
            }
        }

        try:
            await self.node._update_player(self.guild.id, data=request)
        except Exception:
            await self.disconnect()
        else:
            self._connection_event.set()

    async def connect(self, **kwargs: Any):
        self._ensure_channel_id()
        return await super().connect(**kwargs)

class MusicClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
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
            client_id=config["spotify_client_id"],
            client_secret=config["spotify_client_secret"],
        ))
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
                uri=config["node_url"],
                password=config["node_pw"],
            )
            await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)
            print('音樂節點連接成功！')
            await self.tree.sync()
            print("命令已同步！")
        except Exception as e:
            print(f'音樂節點連接失敗：{e}')
    async def on_ready(self):
        print(f'已登入為 {self.user}')
        print("Done!")
        self.add_view(RefreshButton())
        self.add_view(opselect_view())
        self.auto_update_status.start() 
        check_inactive_guilds.start()
        guild = discord.utils.get(self.guilds, id=int(config["discord_guild_id"]))
        voice_channel = discord.utils.get(guild.voice_channels, id=int(config["discord_voice_channel_id"]))
        if voice_channel and not guild.voice_client:
            try:
                await voice_channel.connect(cls=LavalinkPlayerCompat)
            except Exception as e:
                print(f"自動連接語音頻道失敗：{e}")


client = MusicClient()

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

EMBED_COLORS = {
    'success': discord.Color.green(),
    'error': discord.Color.red(),
    'info': discord.Color.blue(),
    'warning': discord.Color.yellow(),
    'spotify': discord.Color.from_rgb(30, 215, 96),
    'youtube': discord.Color.from_rgb(255, 0, 0)
}

class Song:
    def __init__(self, url: str, title: str, duration: int, thumbnail: str, requester: discord.Member, platform: str):
        self.url = url
        self.title = title
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.platform = platform.lower()

class opselect_view(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(opselect())

class LavalinkStatusView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed]):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.previous.disabled = self.current_page == 0
        self.next.disabled = self.current_page >= len(self.embeds) - 1

    @discord.ui.button(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="➡️ 下一頁", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.format_embed(), view=self)

    def format_embed(self):
        embed = self.embeds[self.current_page]
        embed.set_footer(text=f"第 {self.current_page + 1} / {len(self.embeds)} 頁｜總計 {len(self.embeds)} 個伺服器正在播放")
        return embed

class opselect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Lavalink 播放狀態", value="Lavalink 播放狀態"),
            discord.SelectOption(label="更新機器人狀態", value="更新機器人狀態")
        ]
        super().__init__(placeholder="選擇功能", min_values=1, max_values=1, options=options, custom_id="persistent_view:op_select")
    async def callback(self, interaction: discord.Interaction):
        op_select = self.values[0]
        if op_select == "Lavalink 播放狀態":
            embeds = []
            for guild in client.guilds:
                if guild.voice_client and guild.voice_client.playing:
                    current_song = client.current_songs.get(guild.id)
                    queue_length = len(client.queues[guild.id]) if guild.id in client.queues else 0
                    status_parts = []
                    if client.loop_mode.get(guild.id, False):
                        status_parts.append("🔄循環")
                    if client.auto_recommend.get(guild.id, False):
                        status_parts.append("✨推薦")
                    voice_channel = guild.voice_client.channel
                    member_count = len([m for m in voice_channel.members if not m.bot])

                    embed = discord.Embed(
                        title="🎵 Lavalink 播放狀態",
                        description=f"📡 {guild.name}",
                        color=EMBED_COLORS['info']
                    )
                    embed.add_field(name="🎵 播放中", value=current_song.title if current_song else "未知", inline=False)
                    embed.add_field(name="👥 頻道", value=f"{voice_channel.name} ({member_count}人在線)", inline=True)
                    embed.add_field(name="📋 佇列", value=f"{queue_length} 首", inline=True)
                    embed.add_field(name="⚙️ 狀態", value=' | '.join(status_parts) if status_parts else '➡️ 一般播放', inline=False)
                    embeds.append(embed)

            if not embeds:
                embed = discord.Embed(
                    title="🎵 Lavalink 播放狀態",
                    description="目前沒有伺服器正在播放音樂",
                    color=EMBED_COLORS['info']
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                view = LavalinkStatusView(embeds)
                await interaction.response.send_message(embed=view.format_embed(), view=view, ephemeral=True)
        if op_select == "更新機器人狀態":
            for guild in client.guilds:
                if guild.voice_client and guild.voice_client.playing:
                    current_song = client.current_songs.get(guild.id)
                    if current_song:
                        await client.update_presence(current_song.title)
                        await interaction.response.send_message("✅ 已更新音樂機器人狀態顯示", ephemeral=True)
                        return
            await client.update_presence()
            await interaction.response.send_message("✅ 已更新音樂機器人狀態顯示", ephemeral=True)

class RefreshButton(discord.ui.View):
    def __init__(self, image_url: str = None):
        super().__init__(timeout=None)
        if image_url:
            self.add_item(discord.ui.Button(label="點我跳轉", url=image_url, style=discord.ButtonStyle.link))

    @discord.ui.button(label="重新取得", style=discord.ButtonStyle.primary, custom_id="refresh_button")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref_embed = discord.Embed(title="<a:loading:1429472831103832195> 重新取得中...", color=discord.Color.yellow())
        await interaction.response.edit_message(embed=ref_embed, view=None)

        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.redbean0721.com/api/img?type=json") as api_response:
                end_time = datetime.datetime.now()
                if api_response.status != 200:
                    await interaction.edit_original_response(content="無法獲取圖片，請稍後再試。")
                    return
                data = await api_response.json()
                image_url = data.get("url")
                tag = data.get("tag")
                color_task = asyncio.create_task(get_dominant_color(image_url))
                image_task = asyncio.create_task(session.get(image_url))
                image_response = await image_task
                image_bytes = await image_response.read()
                embed_color = await color_task
                elapsed = (end_time - start_time).total_seconds()
                embed = discord.Embed(
                    title="隨機圖",
                    color=embed_color,
                    description=f"提示詞: {tag}",
                )
                file = discord.File(BytesIO(image_bytes), filename="image.jpg")
                embed.set_image(url="attachment://image.jpg")
                embed.set_footer(text=f"回應時間: {elapsed:.2f}s")
                embed.timestamp = datetime.datetime.now()
                view = RefreshButton(image_url=image_url)
                await interaction.edit_original_response(embed=embed, view=view, attachments=[file])

async def get_dominant_color(url):
    def sync_get_color():
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content))
            img = img.resize((50, 50)).convert('RGB')
            pixels = list(img.getdata())
            r_avg = sum(p[0] for p in pixels) // len(pixels)
            g_avg = sum(p[1] for p in pixels) // len(pixels)
            b_avg = sum(p[2] for p in pixels) // len(pixels)
            h, s, v = colorsys.rgb_to_hsv(r_avg/255, g_avg/255, b_avg/255)
            v = max(min(v * 1.5, 1.0), 0.5)
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return discord.Color.from_rgb(int(r*255), int(g*255), int(b*255))
        except:
            return discord.Color.green()

    return await asyncio.to_thread(sync_get_color)