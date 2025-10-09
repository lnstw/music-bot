import os
CONFIG_PATH = "config.txt"
CONFIG_KEYS = [
    "discord_user_name",
    "discord_user_id",
    "spotify_client_id",
    "spotify_client_secret",
    "node_url",
    "node_pw",
    "discord_bot_token"
]
CONFIG_TEMPLATE = """discord_user_name=請填入你的discord名稱
discord_user_id=請填入你的discord_id
spotify_client_id=請填入你的client_id
spotify_client_secret=請填入你的client_secret
node_url=請填入你的lavalink網址
node_pw=請填入你的lavalink密碼
discord_bot_token=請填入你的discord token"""
def check_and_create_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        print("已自動建立 config.txt，請填入相關資訊後重新啟動程式。")
        exit(0)
    config = {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                config[key.strip()] = value.strip()
    missing = [k for k in CONFIG_KEYS if k not in config]
    if missing:
        with open(CONFIG_PATH, "a", encoding="utf-8") as f:
            for k in missing:
                f.write(f"{k}=請填入你的資料\n")
        print(f"config.txt 缺少欄位，已自動補上：{', '.join(missing)}，請補齊後重新啟動。")
        exit(0)
    for k in CONFIG_KEYS:
        if config[k].startswith("請填入"):
            print(f"請在 config.txt 裡填入 {k} 的正確值後再啟動。")
            exit(0)
    return config
config = check_and_create_config()
import discord
from discord import app_commands
from discord.ext import tasks
import wavelink
from typing import Optional, Dict, Any
from collections import deque
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re
from urllib.parse import urlparse, parse_qs
import random
import requests
from PIL import Image
from io import BytesIO
import colorsys
import datetime
from datetime import timedelta
from discord.ui import View, Button
EMBED_COLORS = {
    'success': discord.Color.green(),
    'error': discord.Color.red(),
    'info': discord.Color.blue(),
    'warning': discord.Color.yellow(),
    'spotify': discord.Color.from_rgb(30, 215, 96),
    'youtube': discord.Color.from_rgb(255, 0, 0)
}
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
        self.default_volume = 10
        self.spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=config["spotify_client_id"],
            client_secret=config["spotify_client_secret"],
        ))
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
        print("Done!") # or logging.info
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.streaming,
                name="/help 查看指令"
            )
        )
        guild = discord.utils.get(self.guilds, id=1287276156994981899)
        voice_channel = discord.utils.get(guild.voice_channels, id=1287276156994981903)
        await voice_channel.connect(cls=wavelink.Player)

@tasks.loop(seconds=300)
async def lavalink_keep_alive():
    node = wavelink.NodePool.get_node()
    await node.get_stats()

class Song:
    def __init__(self, url: str, title: str, duration: int, thumbnail: str, requester: discord.Member, platform: str):
        self.url = url
        self.title = title
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.platform = platform.lower()
async def send_message_to_last_channel(guild_id: int, message: str = None, embed: discord.Embed = None):
    if guild_id in client.last_channels:
        guild = client.get_guild(guild_id)
        if guild:
            channel = guild.get_channel(client.last_channels[guild_id])
            if channel:
                try:
                    if embed:
                        await channel.send(embed=embed, silent=True)
                    elif message:
                        await channel.send(message, silent=True)
                except Exception as e:
                    print(f"發送訊息時發生錯誤: {e}")
def create_song_embed(song: Song, position: int) -> discord.Embed:
    platform_info = {
        'youtube': {'color': discord.Color.red(), 'icon': '🎥'},
        'spotify': {'color': discord.Color.green(), 'icon': '🎵'},
        'soundcloud': {'color': discord.Color.orange(), 'icon': '☁️'},
        'bilibili': {'color': discord.Color.blue(), 'icon': '📺'},
        'apple': {'color': discord.Color.from_rgb(255, 45, 85), 'icon': '🍎'}
    }
    platform_data = platform_info.get(song.platform, {
        'color': discord.Color.default(),
        'icon': '🎵'
    })
    embed = discord.Embed(
        title=f"{platform_data['icon']} 已加入播放清單",
        description=f"[{song.title}]({song.url})",
        color=platform_data['color']
    )
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    minutes = song.duration // 60
    seconds = song.duration % 60
    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
    embed.add_field(name="請求者", value=song.requester.mention, inline=True)
    embed.add_field(name="位置", value=f"#{position}", inline=True)
    embed.add_field(name="平台", value=song.platform.title(), inline=True)
    embed.set_footer(text=f"好聽嗎? • 目前清單長度：{position}")
    return embed
def create_now_playing_embed(song: Song) -> discord.Embed:
    platform_info = {
        'youtube': {'color': EMBED_COLORS['youtube'], 'icon': '🎥'},
        'spotify': {'color': EMBED_COLORS['spotify'], 'icon': '🎵'},
        'soundcloud': {'color': discord.Color.orange(), 'icon': '☁️'},
        'bilibili': {'color': discord.Color.blue(), 'icon': '📺'},
        'apple': {'color': discord.Color.from_rgb(255, 45, 85), 'icon': '🍎'}
    }
    original_platform = song.platform.lower()
    platform_data = platform_info.get(original_platform, {
        'color': discord.Color.default(),
        'icon': '🎵'
    })
    embed = discord.Embed(
        title=f"{platform_data['icon']} 正在播放",
        description=f"[{song.title}]({song.url})",
        color=platform_data['color']
    )
    embed.set_footer(text="✅可以使用/nowplaymsg開關此訊息")
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    minutes = song.duration // 60
    seconds = song.duration % 60
    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
    embed.add_field(name="請求者", value=song.requester.mention, inline=True)
    platform_display_names = {
        'youtube': 'YouTube',
        'spotify': 'Spotify',
        'soundcloud': 'SoundCloud',
        'bilibili': 'BiliBili',
        'apple': 'Apple Music'
    }
    display_platform = platform_display_names.get(original_platform, original_platform.title())
    embed.add_field(name="平台(可能不正常)", value=display_platform, inline=True)
    return embed
async def process_spotify_track(spotify_client, url: str) -> Optional[str]:
    try:
        track_id = url.split('track/')[1].split('?')[0]
        track = spotify_client.track(track_id)
        artist_name = track['artists'][0]['name']
        track_name = track['name']
        return f"{track_name} {artist_name} audio"
    except Exception as e:
        print(f"Spotify 處理錯誤: {e}")
        return None
async def process_bilibili_url(url: str) -> Optional[str]:
    try:
        if 'b23.tv' in url:
            url = requests.head(url, allow_redirects=True).url
        bv_match = re.search(r'BV\w+', url)
        if bv_match:
            return f"bilibili {bv_match.group()} audio"
        return None
    except Exception as e:
        print(f"Bilibili 處理錯誤: {e}")
        return None
def get_platform(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        elif 'spotify.com' in domain:
            return 'spotify'
        elif 'soundcloud.com' in domain:
            return 'soundcloud'
        elif 'bilibili.com' in domain or 'b23.tv' in domain:
            return 'bilibili'
        elif 'music.apple.com' in domain:
            return 'apple'
    except:
        pass
    return 'youtube'
client = MusicClient()
def create_error_embed(error_message: str) -> discord.Embed:
    user_name = config["discord_user_name"]
    user_id = int(config["discord_user_id"])
    embed = discord.Embed(
        title="❌ 發生錯誤",
        description=f"{error_message}\n\n如果問題持續發生，請嘗試：\n"
                   f"1️⃣ 使用 `/reload` 重新讓機器人加入\n"
                   f"2️⃣ 重新加入語音頻道\n"
                   f"3️⃣ 聯絡機器人作者 {user_name} <@{user_id}>",
        color=EMBED_COLORS['error']
    )
    embed.set_footer(text="機器人錯誤回報")
    return embed
@client.tree.command(name="play", description="播放音樂")
async def play(interaction: discord.Interaction, query: str):
    guild_id = interaction.guild_id
    client.force_stop[guild_id] = False
    try:
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        is_playlist = False
        if 'spotify.com' in query:
            if 'playlist' in query or 'album' in query:
                is_playlist = True
        elif 'youtube.com' in query or 'youtu.be' in query:
            if 'list=' in query:
                is_playlist = True
        elif 'music.apple.com' in query:
            if 'playlist' in query or 'album' in query:
                is_playlist = True
        if is_playlist:
            platform = get_platform(query)
            search_queries = []
            try:
                if platform == 'spotify':
                    if 'playlist' in query.lower():
                        search_queries = await process_spotify_playlist(client.spotify, query)
                    elif 'album' in query.lower():
                        search_queries = await process_spotify_album(client.spotify, query)
                elif platform == 'youtube':
                    if 'list=' in query:
                        search_queries = await process_youtube_playlist(query)
                if not search_queries:
                    embed = discord.Embed(
                        title="❌ 無法處理播放清單",
                        description="播放清單可能是空的或無法訪問",
                        color=EMBED_COLORS['error']
                    )
                    await interaction.followup.send(embed=embed)
                    return
                if not interaction.guild.voice_client:
                    try:
                        vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                    except Exception as e:
                        error_embed = create_error_embed(f"無法連接語音頻道：{str(e)}")
                        await interaction.followup.send(embed=error_embed)
                        return
                else:
                    vc: wavelink.Player = interaction.guild.voice_client
                await vc.set_volume(client.default_volume)
                if guild_id not in client.queues:
                    client.queues[guild_id] = deque()
                client.last_channels[guild_id] = interaction.channel_id
                await process_playlist(interaction, search_queries, "播放清單")
            except Exception as e:
                print(f"處理播放清單時發生錯誤: {e}")
                error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}")
                await interaction.followup.send(embed=error_embed)
                return
        else:
            try:
                if not interaction.user.voice:
                    embed = discord.Embed(
                        title="❌ 無法播放",
                        description="請先加入語音頻道",
                        color=EMBED_COLORS['error']
                    )
                    await interaction.followup.send(embed=embed)
                    return
                platform = get_platform(query)
                search_queries = []
                try:
                    if platform == 'spotify':
                        if 'playlist' in query.lower():
                            search_queries = await process_spotify_playlist(client.spotify, query)
                        elif 'album' in query.lower():
                            search_queries = await process_spotify_album(client.spotify, query)
                        else:
                            search_query = await process_spotify_track(client.spotify, query)
                            if search_query:
                                search_queries = [search_query]
                    elif platform == 'youtube':
                        if 'playlist' in query.lower() or 'list=' in query:
                            search_queries = await process_youtube_playlist(query)
                        else:
                            search_queries = [query]
                    elif platform == 'bilibili':
                        search_query = await process_bilibili_url(query)
                        if search_query:
                            search_queries = [search_query]
                    else:
                        search_queries = [query]
                    if not search_queries:
                        embed = discord.Embed(
                            title="❌ 無法處理連結",
                            description="無法解析此連結，請嘗試其他連結或直接搜尋歌名",
                            color=EMBED_COLORS['error']
                        )
                        await interaction.followup.send(embed=embed)
                        return
                except Exception as e:
                    print(f"URL 處理錯誤: {e}")
                    embed = discord.Embed(
                        title="❌ 無法處理連結",
                        description="處理連結時發生錯誤，請嘗試其他連結或直接搜尋歌名",
                        color=EMBED_COLORS['error']
                    )
                    await interaction.followup.send(embed=embed)
                    return
                if not interaction.guild.voice_client:
                    try:
                        vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                    except Exception as e:
                        error_embed = create_error_embed(f"無法連接語音頻道：{str(e)}")
                        await interaction.followup.send(embed=error_embed)
                        return
                else:
                    vc: wavelink.Player = interaction.guild.voice_client
                await vc.set_volume(client.default_volume)
                guild_id = interaction.guild_id
                if guild_id not in client.queues:
                    client.queues[guild_id] = deque()
                client.last_channels[guild_id] = interaction.channel_id
                try:
                    tracks = await wavelink.Playable.search(search_queries[0])
                    if tracks:
                        track = tracks[0]
                        song = Song(
                            url=track.uri,
                            title=track.title,
                            duration=int(track.length // 1000),
                            thumbnail=track.artwork,
                            requester=interaction.user,
                            platform=platform
                        )
                        client.queues[guild_id].append(song)
                        embed = create_song_embed(song, len(client.queues[guild_id]))
                        await interaction.followup.send(embed=embed)
                        if not vc.playing:
                            await play_next(interaction.guild, vc)
                    else:
                        embed = discord.Embed(
                            title="❌ 無法找到歌曲",
                            description="請嘗試其他連結或直接搜尋歌名",
                            color=EMBED_COLORS['error']
                        )
                        await interaction.followup.send(embed=embed)
                except Exception as e:
                    print(f"播放歌曲時發生錯誤：{str(e)}")
                    error_embed = create_error_embed(f"播放歌曲時發生錯誤：{str(e)}")
                    await interaction.followup.send(embed=error_embed)
            except Exception as e:
                print(f"播放指令發生錯誤：{str(e)}")
                error_embed = create_error_embed(f"播放指令發生錯誤：{str(e)}")
                await interaction.followup.send(embed=error_embed)
    except Exception as e:
                print(f"播放指令發生錯誤：{str(e)}")
                error_embed = create_error_embed(f"播放指令發生錯誤：{str(e)}")
                await interaction.followup.send(embed=error_embed)
async def process_spotify_url(url: str) -> list[str]:
    try:
        if 'playlist' in url:
            playlist_id = url.split('playlist/')[1].split('?')[0]
            results = client.spotify.playlist_tracks(playlist_id)
            tracks = []
            while results:
                for item in results['items']:
                    track = item['track']
                    if track:
                        artist_name = track['artists'][0]['name']
                        track_name = track['name']
                        tracks.append(f"{track_name} {artist_name}")
                if results['next']:
                    results = client.spotify.next(results)
                else:
                    break
            return tracks
        elif 'track' in url:
            track_id = url.split('track/')[1].split('?')[0]
            track = client.spotify.track(track_id)
            artist_name = track['artists'][0]['name']
            track_name = track['name']
            return [f"{track_name} {artist_name}"]
        elif 'album' in url:
            album_id = url.split('album/')[1].split('?')[0]
            results = client.spotify.album_tracks(album_id)
            return [f"{track['name']} {track['artists'][0]['name']}" 
                   for track in results['items']]
    except Exception as e:
        print(f"Spotify 處理錯誤: {e}")
        return []
async def update_presence(status: str = None):
    if status:
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{status} | /help 查看指令"
            )
        )
    else:
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.streaming,
                name="/help 查看指令"
            )
        )
async def get_next_recommendation(guild_id: int) -> Optional[Song]:
    try:
        if guild_id in client.current_songs:
            current_song = client.current_songs[guild_id]
            return await get_recommendations(current_song)
    except Exception as e:
        print(f"獲取下一個推薦時發生錯誤：{e}")
    return None
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
            await play_next(guild, payload.player)
        else:
            await update_presence()
            embed = discord.Embed(
                title="✅ 播放完成",
                description="播放清單已播放完畢",
                color=EMBED_COLORS['success']
            )
            await send_message_to_last_channel(guild_id, embed=embed)
    except Exception as e:
        print(f"處理歌曲結束時發生錯誤：{e}")
        if payload.player and payload.player.guild:
            error_embed = create_error_embed(f"處理歌曲結束時發生錯誤：{str(e)}")
            await send_message_to_last_channel(payload.player.guild.id, embed=error_embed)
@client.tree.command(name="pause", description="暫停播放")
async def pause(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    if not interaction.guild.voice_client:
        embed = discord.Embed(
            title="❌ 無法暫停",
            description="機器人不在語音頻道中",
            color=EMBED_COLORS['error']
        )
        await interaction.response.send_message(embed=embed)
        return
    vc: wavelink.Player = interaction.guild.voice_client
    if not vc.playing:
        embed = discord.Embed(
            title="❌ 無法暫停",
            description="目前沒有播放任何歌曲",
            color=EMBED_COLORS['error']
        )
        await interaction.response.send_message(embed=embed)
        return
    try:
        if vc.paused:
            embed = discord.Embed(
                title="⚠️ 已經暫停",
                description="音樂已經處於暫停狀態",
                color=EMBED_COLORS['warning']
            )
            await interaction.response.send_message(embed=embed)
            return
        await vc.pause(True)
        embed = discord.Embed(
            title="⏸️ 已暫停",
            description="音樂已暫停播放",
            color=EMBED_COLORS['success']
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"暫停時發生錯誤：{e}")
        embed = create_error_embed(f"暫停時時發生錯誤：{str(e)}")
        await interaction.response.send_message(embed=embed)
@client.tree.command(name="resume", description="繼續播放")
async def resume(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    if not interaction.guild.voice_client:
        embed = discord.Embed(
            title="❌ 無法繼續播放",
            description="機器人不在語音頻道中",
            color=EMBED_COLORS['error']
        )
        await interaction.response.send_message(embed=embed)
        return
    vc: wavelink.Player = interaction.guild.voice_client
    if not vc.playing:
        embed = discord.Embed(
            title="❌ 無法繼續播放",
            description="目前沒有播放任何歌曲",
            color=EMBED_COLORS['error']
        )
        await interaction.response.send_message(embed=embed)
        return
    try:
        if not vc.paused:
            embed = discord.Embed(
                title="⚠️ 已在播放中",
                description="音樂已經在播放中",
                color=EMBED_COLORS['warning']
            )
            await interaction.response.send_message(embed=embed)
            return
        await vc.pause(False)
        embed = discord.Embed(
            title="▶️ 繼續播放",
            description="音樂已繼續播放",
            color=EMBED_COLORS['success']
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"繼續播放時發生錯誤：{e}")
        embed = create_error_embed(f"繼續播放時發生錯誤：{str(e)}")
        await interaction.response.send_message(embed=embed)
@client.tree.command(name="stop", description="停止播放並清空播放清單")
async def stop(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ 沒有歌曲正在播放！")
        return
    vc: wavelink.Player = interaction.guild.voice_client
    guild_id = interaction.guild_id
    if not hasattr(client, "force_stop"):
        client.force_stop = {}
    client.force_stop[guild_id] = True
    if vc.playing:
        await vc.stop()
    if guild_id in client.queues:
        client.queues[guild_id].clear()
    if guild_id in client.current_songs:
        del client.current_songs[guild_id]
    if guild_id in client.loop_mode:
        client.loop_mode[guild_id] = False  # 關閉循環模式
    if guild_id in client.auto_recommend:
        client.auto_recommend[guild_id] = False
    vc.queue.clear()
    await update_presence()
    embed = discord.Embed(
        title="⏹️ 已停止播放",
        description="已清空播放清單並關閉循環模式",
        color=EMBED_COLORS['success']
    )
    if guild_id in client.auto_recommend and client.auto_recommend[guild_id]:
        embed.set_footer(text="自動推薦功能仍然開啟")
    await interaction.response.send_message(embed=embed)
@client.tree.command(name="skip", description="跳過當前歌曲")
async def skip(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ 沒有歌曲正在播放！")
        return
    vc: wavelink.Player = interaction.guild.voice_client
    guild_id = interaction.guild_id
    if not vc.playing:
        await interaction.response.send_message("❌ 沒有歌曲正在播放！")
        return
    next_song = None
    if client.loop_mode.get(guild_id, False) and client.queues[guild_id]:
        current_song = client.current_songs[guild_id]
        queue_list = list(client.queues[guild_id])
        current_index = queue_list.index(current_song)
        next_index = (current_index + 1) % len(queue_list)
        next_song = queue_list[next_index]
    elif client.queues[guild_id]:
        next_song = client.queues[guild_id][0]
    embed = discord.Embed(
        title="⏭️ 已跳過當前歌曲",
        color=EMBED_COLORS['success']
    )
    if next_song:
        embed.add_field(
            name="即將播放",
            value=f"[{next_song.title}]({next_song.url})",
            inline=False
        )
    await interaction.response.send_message(embed=embed)
    await vc.stop()  # 停止當前播放，觸發 play_next
async def play_next(guild: discord.Guild, vc: wavelink.Player):
    guild_id = guild.id
    if client.force_stop.get(guild_id, False):
        await update_presence()
        embed = discord.Embed(
                title="✅ 播放完成",
                description="播放清單已播放完畢",
                color=EMBED_COLORS['success']
        )
        await send_message_to_last_channel(guild_id, embed=embed)
        return
    try:
        if not client.queues[guild_id]:
            if client.loop_mode.get(guild_id, False) and guild_id in client.current_songs:
                current_song = client.current_songs[guild_id]
                client.queues[guild_id].append(current_song)
            elif (guild_id in client.auto_recommend and 
                  client.auto_recommend[guild_id] and 
                  guild_id in client.current_songs):
                recommended_song = await get_next_recommendation(guild_id)
                if recommended_song:
                    client.queues[guild_id].append(recommended_song)
        if client.queues[guild_id]:
            if client.loop_mode.get(guild_id, False):
                current_song = client.current_songs.get(guild_id)
                queue_list = list(client.queues[guild_id])
                if current_song in queue_list:
                    current_index = queue_list.index(current_song)
                    next_index = (current_index + 1) % len(queue_list)
                    next_song = queue_list[next_index]
                    client.queues[guild_id] = deque(queue_list[next_index:] + queue_list[:next_index])
                else:
                    next_song = queue_list[0]
            else:
                next_song = client.queues[guild_id].popleft()
            client.current_songs[guild_id] = next_song
            if client.loop_mode.get(guild_id, False) and next_song not in client.queues[guild_id]:
                client.queues[guild_id].append(next_song)
            try:
                tracks = await wavelink.Playable.search(next_song.url)
                if tracks:
                    track = tracks[0]
                    await vc.play(track)
                    await update_presence(next_song.title)
                    if client.show_now_song.get(guild_id, True):
                        embed = create_now_playing_embed(next_song)
                        if client.loop_mode.get(guild_id, False):
                            queue_list = list(client.queues[guild_id])
                            total = len(queue_list)
                            embed.set_footer(text=f"🔄 循環播放中 總共 {total} 首")
                        await send_message_to_last_channel(guild_id, embed=embed)
            except Exception as e:
                print(f"播放歌曲時發生錯誤: {e}")
                await play_next(guild, vc)
        else:
            await update_presence()
            embed = discord.Embed(
                title="✅ 播放完成",
                description="播放清單已播放完畢",
                color=EMBED_COLORS['success']
            )
            await send_message_to_last_channel(guild_id, embed=embed)
    except Exception as e:
        print(f"播放下一首時發生錯誤：{e}")
        error_embed = create_error_embed(f"播放時發生錯誤：{str(e)}")
        await send_message_to_last_channel(guild_id, embed=error_embed)
@client.tree.command(name="volume", description="調整音量")
@app_commands.describe(volume="音量大小 (0-150)")
async def volume(interaction: discord.Interaction, volume: int):
    try:
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.response.send_message("❌ 機器人不在語音頻道中！")
            return
        if not 0 <= volume <= 150:
            await interaction.response.send_message("❌ 音量必須在 0-150 之間！")
            return
        client.default_volume = volume  # 更新全局音量
        vc: wavelink.Player = interaction.guild.voice_client
        await vc.set_volume(volume)  # 設定當前播放器的音量
        await interaction.response.send_message(f"🔊 音量已設定為 {volume}%")
    except Exception as e:
        print(f"調整音量時發生錯誤：{str(e)}")
        error_embed = create_error_embed(f"調整音量時發生錯誤：{str(e)}")
        await interaction.response.send_message(embed=error_embed)
@client.tree.command(name="loop", description="切換循環播放模式")
async def loop(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if not hasattr(client, 'loop_mode'):
        client.loop_mode = {}
    client.loop_mode[guild_id] = not client.loop_mode.get(guild_id, False)
    if client.loop_mode[guild_id]:
        if guild_id in client.current_songs:
            current_song = client.current_songs[guild_id]
            if current_song not in client.queues[guild_id]:
                client.queues[guild_id].append(current_song)
    status = "開啟" if client.loop_mode[guild_id] else "關閉"
    embed = discord.Embed(
        title="🔄 循環播放設置",
        description=f"循環播放已{status}",
        color=EMBED_COLORS['success']
    )
    if client.loop_mode[guild_id]:
        total_songs = len(client.queues[guild_id])
        embed.add_field(
            name="循環清單",
            value=f"目前共有 {total_songs} 首歌曲在循環播放中",
            inline=False
        )
    await interaction.response.send_message(embed=embed)
@client.tree.command(name="shuffle", description="隨機播放清單")
async def shuffle(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if guild_id not in client.queues or not client.queues[guild_id]:
        await interaction.response.send_message("❌ 播放清單是空的！")
        return
    if client.loop_mode.get(guild_id, False):
        current_song = client.current_songs.get(guild_id)
        queue_list = list(client.queues[guild_id])
        if current_song in queue_list:
            queue_list.remove(current_song)
        random.shuffle(queue_list)
        if current_song:
            queue_list.append(current_song)
        client.queues[guild_id] = deque(queue_list)
    else:
        queue_list = list(client.queues[guild_id])
        random.shuffle(queue_list)
        client.queues[guild_id] = deque(queue_list)
    embed = discord.Embed(
        title="🔀 已隨機排序播放清單",
        description=f"已重新排序 {len(client.queues[guild_id])} 首歌曲",
        color=EMBED_COLORS['success']
    )
    if client.loop_mode.get(guild_id, False):
        embed.set_footer(text="🔄 循環模式開啟中")
    await interaction.response.send_message(embed=embed)
class QueuePaginator(View):
    def __init__(self, interaction, queue_list, songs_per_page=10, current_song=None, status_parts=None):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.queue_list = queue_list
        self.songs_per_page = songs_per_page
        self.current_song = current_song
        self.total_pages = (len(queue_list) + songs_per_page - 1) // songs_per_page or 1
        self.page = 0
        self.status_parts = status_parts or []
        self.prev_button = Button(label="上一頁", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="下一頁", style=discord.ButtonStyle.primary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    def get_embed(self):
        start_idx = self.page * self.songs_per_page
        end_idx = min(start_idx + self.songs_per_page, len(self.queue_list))
        embed = discord.Embed(
            title=f"📃 播放清單 (第 {self.page+1}/{self.total_pages} 頁)",
            color=EMBED_COLORS['info']
        )
        if self.status_parts:
            embed.description = " | ".join(self.status_parts)
        if self.current_song:
            duration = f"{self.current_song.duration//60}:{self.current_song.duration%60:02d}"
            current_text = f"[{self.current_song.title}]({self.current_song.url})\n`{duration}` | {self.current_song.requester.mention}"
            embed.add_field(name="🎵 正在播放", value=current_text, inline=False)
        description = ""
        char_limit = 1024
        for idx, song in enumerate(self.queue_list[start_idx:end_idx], start=start_idx+1):
            duration = f"{song.duration//60}:{song.duration%60:02d}"
            line = f"`{idx}.` [{song.title}]({song.url}) | `{duration}`\n"
            # 若超過 Discord embed field 限制，截斷
            if len(description) + len(line) > char_limit:
                description += f"...（已自動截斷，請翻頁查看更多）"
                break
            description += line
        if not description:
            description = "播放清單是空的"
        embed.add_field(
            name=f"📋 待播清單 ({start_idx+1}-{min(end_idx, len(self.queue_list))}/{len(self.queue_list)})",
            value=description,
            inline=False
        )
        total_duration = sum(s.duration for s in self.queue_list)
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        if len(self.queue_list) > 0:
            if hours > 0:
                embed.set_footer(text=f"總時長: {hours}:{minutes:02d}:00")
            else:
                embed.set_footer(text=f"總時長: {minutes}:00")
        return embed

    async def prev_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

@client.tree.command(name="queue", description="顯示播放清單")
async def queue(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        if guild_id not in client.queues:
            client.queues[guild_id] = deque()
        queue_list = list(client.queues[guild_id])
        current_song = client.current_songs.get(guild_id)
        status_parts = []
        is_loop = client.loop_mode.get(guild_id, False)
        if is_loop:
            status_parts.append("🔄 循環模式：開啟")
        if guild_id in client.auto_recommend and client.auto_recommend[guild_id]:
            status_parts.append("✨ 自動推薦：開啟")
        paginator = QueuePaginator(interaction, queue_list, songs_per_page=10, current_song=current_song, status_parts=status_parts)
        embed = paginator.get_embed()
        await interaction.followup.send(embed=embed, view=paginator)
    except Exception as e:
        print(f"顯示播放清單時發生錯誤：{str(e)}")
        error_embed = create_error_embed(f"顯示播放清單時發生錯誤：{str(e)}")
        await interaction.followup.send(embed=error_embed)
@client.tree.command(name="help", description="顯示指令說明")
async def help(interaction: discord.Interaction):
    commands = await client.tree.fetch_commands()
    cmd_dict = {cmd.name: cmd.id for cmd in commands}
    embed = discord.Embed(
        title="🎵 音樂機器人指令說明",
        description="以下是所有可用的指令：",
        color=EMBED_COLORS['info']
    )
    commands_info = {
        "play": "播放音樂 (支援 YouTube/Spotify/Bilibili)",
        "playnext": "將歌曲插入到播放清單的下一個位置",
        "pause": "暫停當前播放的歌曲",
        "resume": "繼續播放歌曲",
        "skip": "跳過當前播放的歌曲",
        "stop": "停止播放並清空播放清單",
        "queue": "顯示播放清單",
        "clear": "清空播放清單",
        "remove": "從播放清單中移除指定歌曲",
        "shuffle": "隨機排序播放清單",
        "loop": "切換循環播放模式",
        "autorecommend": "開啟/關閉自動推薦功能",
        "np": "顯示當前播放的歌曲",
        "volume": "調整音量 (0-150)",
        "nowplaymsg": "開啟/關閉目前播放歌曲的提示訊息",
        "leave": "讓機器人離開語音頻道",
        "reload": "重新載入音樂播放 (修復問題用)",
        "隨機圖": "可以隨機給你一張圖片"
    }
    for cmd_name, desc in commands_info.items():
        cmd_id = cmd_dict.get(cmd_name, "00")
        embed.add_field(name=f"</{cmd_name}:{cmd_id}>", value=desc, inline=False)
    embed.add_field(
        name="🔄 循環播放",
        value="重複播放整個清單\n• 新歌曲會加入循環\n• 可用playnext插入歌曲\n• shuffle可以打亂清單",
        inline=False  
    )
    embed.add_field(
        name="✨ 自動推薦",
        value="清單空時會推薦相似歌曲\n• 保持相似風格\n• 循環模式完整播完後才推薦",
        inline=False
    )
    await interaction.response.send_message(embed=embed)
@client.tree.command(name="leave", description="讓機器人離開語音頻道")
async def leave(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.move_members:
        if not await check_voice_state_and_respond(interaction):
            return
    else:
        pass
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ 機器人不在語音頻道中！")
        return
    vc: wavelink.Player = interaction.guild.voice_client
    await vc.disconnect()
    guild_id = interaction.guild_id
    if guild_id in client.queues:
        client.queues[guild_id].clear()
    if guild_id in client.current_songs:
        del client.current_songs[guild_id]
    await interaction.response.send_message("👋 已離開語音頻道")
    await update_presence()
@client.tree.command(name="np", description="顯示當前播放的歌曲")
async def now_playing(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        vc = interaction.guild.voice_client
        if not vc or not vc.playing:
            await interaction.followup.send("❌ 目前沒有播放任何歌曲")
            return
        if guild_id not in client.current_songs:
            await interaction.followup.send("❌ 無法獲取當前歌曲信息")
            return
        song = client.current_songs[guild_id]
        try:
            duration = song.duration
            position = int(vc.position) // 1000  # 轉換為秒
            position = min(position, duration)
            bar_length = 20
            filled = int((position / duration) * bar_length) if duration > 0 else 0
            progress_bar = "▬" * filled + "🔘" + "▬" * (bar_length - filled)
            current_time = f"{position // 60}:{position % 60:02d}"
            total_time = f"{duration // 60}:{duration % 60:02d}"
        except Exception as e:
            print(f"計算進度時發生錯誤：{e}")
            progress_bar = "▬" * 20
            current_time = "0:00"
            total_time = "0:00"
        embed = discord.Embed(
            title="🎵 正在播放",
            description=f"[{song.title}]({song.url})",
            color=discord.Color.blue()
        )
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.add_field(
            name="進度", 
            value=f"{progress_bar}\n{current_time} / {total_time}", 
            inline=False
        )
        embed.add_field(name="請求者", value=song.requester.mention, inline=True)
        loop_status = "🔄 開啟" if client.loop_mode.get(guild_id, False) else "➡️ 關閉"
        embed.add_field(name="循環播放", value=loop_status, inline=True)
        volume = getattr(vc, 'volume', 100)
        embed.add_field(name="音量", value=f"🔊 {volume}%", inline=True)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"NP 命令發生錯誤：{e}")
        await interaction.followup.send(f"❌ 發生錯誤：{str(e)}")
@client.tree.command(name="reload", description="重新載入音樂播放 (重新連接機器人)")
async def reload(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        guild_id = interaction.guild_id
        if not await check_voice_state_and_respond(interaction):
            return
        current_channel = interaction.user.voice.channel
        current_queue = None
        current_song = None
        current_position = 0
        loop_status = client.loop_mode.get(guild_id, False)
        volume = client.default_volume  # 使用全局音量
        auto_recommend_status = client.auto_recommend.get(guild_id, False)  # 保存自動推薦狀態
        if interaction.guild.voice_client:
            vc: wavelink.player = interaction.guild.voice_client
            if vc.playing:
                current_position = int(vc.position)
        if guild_id in client.queues:
            current_queue = list(client.queues[guild_id])
        if guild_id in client.current_songs:
            current_song = client.current_songs[guild_id]
        if interaction.guild.voice_client:
            try:
                vc: wavelink.player = interaction.guild.voice_client
                await vc.disconnect()
                await asyncio.sleep(1)  # 等待斷開連接完成
            except Exception as e:
                print(f"斷開連接時發生錯誤：{e}")
        try:
            vc: wavelink.Player = await current_channel.connect(cls=wavelink.Player)
            await vc.set_volume(volume)  # 設置為全局音量
            if current_queue:
                client.queues[guild_id] = deque(current_queue)
            if current_song:
                client.current_songs[guild_id] = current_song
            client.loop_mode[guild_id] = loop_status
            client.auto_recommend[guild_id] = auto_recommend_status  # 恢復自動推薦狀態
            if current_song:
                try:
                    tracks = await wavelink.Playable.search(current_song.url)
                    if tracks:
                        track = tracks[0]
                        await vc.play(track)
                        if current_position > 0:
                            await asyncio.sleep(0.5)
                            await vc.seek(current_position)
                        embed = discord.Embed(
                            title="✅ 重新載入成功",
                            description=f"已恢復播放：[{current_song.title}]({current_song.url})",
                            color=EMBED_COLORS['success']
                        )
                        embed.add_field(
                            name="播放進度", 
                            value=f"{current_position//1000//60}:{(current_position//1000)%60:02d}",
                            inline=True
                        )
                        if current_queue:
                            embed.add_field(
                                name="佇列歌曲數", 
                                value=str(len(current_queue)),
                                inline=True
                            )
                        embed.add_field(
                            name="循環模式", 
                            value="開啟" if loop_status else "關閉",
                            inline=True
                        )
                        embed.add_field(
                            name="音量", 
                            value=volume,
                            inline=True
                        )
                except Exception as e:
                    print(f"恢復播放時發生錯誤：{e}")
                    await play_next(interaction.guild, vc)
                    embed = discord.Embed(
                        title="⚠️ 部分重新載入成功",
                        description="無法恢復當前歌曲的播放進度，已開始播放下一首",
                        color=EMBED_COLORS['warning']
                    )
            else:
                embed = discord.Embed(
                    title="✅ 重新載入成功",
                    description="已重新連接到語音頻道",
                    color=EMBED_COLORS['success']
                )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"重新連接時發生錯誤：{e}")
            error_embed = create_error_embed(
                f"重新連接時發生錯誤：{str(e)}\n"
                "請確保：\n"
                "1. 機器人有權限加入該語音頻道\n"
                "2. 語音頻道未滿\n"
                "3. 網路連接正常"
            )
            await interaction.followup.send(embed=error_embed)
    except Exception as e:
        print(f"重新載入時發生錯誤：{str(e)}")
        error_embed = create_error_embed(f"重新載入時發生錯誤：{str(e)}")
        await interaction.followup.send(embed=error_embed)
@client.tree.command(name="autorecommend", description="開啟/關閉自動推薦功能")
async def autorecommend(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if guild_id not in client.auto_recommend:
        client.auto_recommend[guild_id] = False
    client.auto_recommend[guild_id] = not client.auto_recommend[guild_id]
    status = "開啟" if client.auto_recommend[guild_id] else "關閉"
    embed = discord.Embed(
        title="✨ 自動推薦設置",
        description=f"自動推薦功能已{status}",
        color=EMBED_COLORS['success']
    )
    embed.set_footer(text="當播放清單為空時，將自動添加相似歌曲")
    await interaction.response.send_message(embed=embed)
@client.tree.command(name="remove", description="從播放清單中移除指定歌曲")
@app_commands.describe(position="要移除的歌曲位置")
async def remove(interaction: discord.Interaction, position: int):
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if guild_id not in client.queues or not client.queues[guild_id]:
        await interaction.response.send_message("❌ 播放清單是空的！")
        return
    queue_list = list(client.queues[guild_id])
    if position < 1 or position > len(queue_list):
        await interaction.response.send_message("❌ 無效的歌曲位置！")
        return
    if client.loop_mode.get(guild_id, False):
        current_song = client.current_songs.get(guild_id)
        if current_song == queue_list[position-1]:
            await interaction.response.send_message("❌ 無法移除當前播放的歌曲！")
            return
    removed_song = queue_list.pop(position-1)
    client.queues[guild_id] = deque(queue_list)
    embed = discord.Embed(
        title="🗑️ 已移除歌曲",
        description=f"已從播放清單中移除：[{removed_song.title}]({removed_song.url})",
        color=EMBED_COLORS['success']
    )
    if client.loop_mode.get(guild_id, False):
        embed.set_footer(text="🔄 循環模式開啟中")
    await interaction.response.send_message(embed=embed)
@client.tree.command(name="clear", description="清空播放清單")
async def clear(interaction: discord.Interaction):
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if not interaction.guild.voice_client:
        await interaction.response.send_message("❌ 機器人不在語音頻道中！")
        return
    if guild_id not in client.queues:
        client.queues[guild_id] = deque()
    if not client.queues[guild_id]:
        await interaction.response.send_message("❌ 播放清單已經是空的！")
        return
    if client.loop_mode.get(guild_id, False) and guild_id in client.current_songs:
        current_song = client.current_songs[guild_id]
        client.queues[guild_id].clear()
        client.queues[guild_id].append(current_song)
        embed = discord.Embed(
            title="🗑️ 已清空播放清單",
            description="已清空播放清單，但保留當前播放歌曲",
            color=EMBED_COLORS['success']
        )
        embed.set_footer(text="🔄 循環模式開啟中")
    else:
        client.queues[guild_id].clear()
        if guild_id in client.current_songs:
            del client.current_songs[guild_id]  # 清除當前歌曲記錄
        if guild_id in client.loop_mode:
            client.loop_mode[guild_id] = False  # 關閉循環模式
        embed = discord.Embed(
            title="🗑️ 已清空播放清單",
            description="已清空所有歌曲並關閉循環模式",
            color=EMBED_COLORS['success']
        )
    await interaction.response.send_message(embed=embed)
@client.tree.command(name="playnext", description="將歌曲插入到播放清單的下一個位置")
async def playnext(interaction: discord.Interaction, query: str):
    try:
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            try:
                vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
                await vc.set_volume(client.default_volume)
            except Exception as e:
                error_embed = create_error_embed(f"無法連接語音頻道：{str(e)}")
                await interaction.followup.send(embed=error_embed)
                return
        else:
            vc: wavelink.Player = interaction.guild.voice_client
        guild_id = interaction.guild_id
        if guild_id not in client.queues:
            client.queues[guild_id] = deque()
        client.last_channels[guild_id] = interaction.channel_id
        search_queries = []
        platform = get_platform(query)
        try:
            if platform == 'spotify':
                if 'playlist' in query.lower() or 'album' in query.lower():
                    embed = discord.Embed(
                        title="⚠️ 不支援的功能",
                        description="插播功能不支援播放清單或專輯",
                        color=EMBED_COLORS['warning']
                    )
                    await interaction.followup.send(embed=embed)
                    return
                elif 'track' in query.lower():
                    search_query = await process_spotify_track(client.spotify, query)
                    if search_query:
                        search_queries = [search_query]
            elif platform == 'youtube':
                if 'playlist' in query.lower() or 'list=' in query:
                    embed = discord.Embed(
                        title="⚠️ 不支援的功能",
                        description="插播功能不支援播放清單",
                        color=EMBED_COLORS['warning']
                    )
                    await interaction.followup.send(embed=embed)
                    return
                else:
                    search_queries = [query]
            elif platform == 'bilibili':
                search_query = await process_bilibili_url(query)
                if search_query:
                    search_queries = [search_query]
            else:
                search_queries = [query]
            if not search_queries:
                embed = discord.Embed(
                    title="❌ 處理失敗",
                    description="無法處理該連結",
                    color=EMBED_COLORS['error']
                )
                await interaction.followup.send(embed=embed)
                return
            tracks = await wavelink.Playable.search(search_queries[0])
            if tracks:
                track = tracks[0]
                song = Song(
                    url=track.uri,
                    title=track.title,
                    duration=int(track.length // 1000),
                    thumbnail=track.artwork,
                    requester=interaction.user,
                    platform=platform
                )
                queue_list = list(client.queues[guild_id])
                if client.loop_mode.get(guild_id, False):
                    current_song = client.current_songs.get(guild_id)
                    if current_song in queue_list:
                        insert_pos = queue_list.index(current_song) + 1
                    else:
                        insert_pos = 0
                    queue_list.insert(insert_pos, song)
                else:
                    queue_list.insert(0, song)
                client.queues[guild_id] = deque(queue_list)
                embed = discord.Embed(
                    title="⏭️ 已加入下一首播放",
                    description=f"[{song.title}]({song.url})",
                    color=EMBED_COLORS['success']
                )
                if song.thumbnail:
                    embed.set_thumbnail(url=song.thumbnail)
                minutes = song.duration // 60
                seconds = song.duration % 60
                embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
                embed.add_field(name="請求者", value=song.requester.mention, inline=True)
                embed.add_field(name="平台", value=platform.title(), inline=True)
                await interaction.followup.send(embed=embed)
                if not vc.playing:
                    await play_next(interaction.guild, vc)
            else:
                embed = discord.Embed(
                    title="❌ 無法找到歌曲",
                    description="請嘗試其他連結或直接搜尋歌名",
                    color=EMBED_COLORS['error']
                )
                await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"插播時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"插播時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=error_embed)
    except Exception as e:
        print(f"插播時發生錯誤：{str(e)}")
        error_embed = create_error_embed(f"插播時發生錯誤：{str(e)}")
        await interaction.followup.send(embed=error_embed)
async def get_dominant_color(url):
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        img = img.resize((50, 50))
        img = img.convert('RGB')
        pixels = list(img.getdata())
        r_total = sum(pixel[0] for pixel in pixels)
        g_total = sum(pixel[1] for pixel in pixels)
        b_total = sum(pixel[2] for pixel in pixels)
        pixel_count = len(pixels)
        r_avg = r_total // pixel_count
        g_avg = g_total // pixel_count
        b_avg = b_total // pixel_count
        h, s, v = colorsys.rgb_to_hsv(r_avg/255, g_avg/255, b_avg/255)
        v = max(min(v * 1.5, 1.0), 0.5)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return discord.Color.from_rgb(int(r*255), int(g*255), int(b*255))
    except:
        return discord.Color.green()
@client.tree.command(name="隨機圖", description="可以隨機給你一張圖片")
async def img(interaction: discord.Interaction):
    await interaction.response.defer()
    api =  requests.get("https://api.redbean0721.com/api/img?type=json")
    if api.status_code == 200:
        data = api.json()
        image_url = data.get("url")
        embed_color = await get_dominant_color(image_url)
        embed = discord.Embed(
            title="隨機圖",
            color=embed_color,
            description=f"提示詞: {data.get('tag')}",
        )
        response = requests.get(image_url)
        file = discord.File(BytesIO(response.content), filename="image.jpg")
        embed.set_image(url="attachment://image.jpg")
        embed.set_footer(text=f"回應時間: {api.elapsed.total_seconds():.2f}s")
        embed.timestamp = datetime.datetime.now()
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="點我跳轉", url=image_url, style=discord.ButtonStyle.link))
        await interaction.followup.send(embed=embed, view=view, file=file)
    else:
        await interaction.followup.send("無法獲取圖片，請稍後再試。")
async def process_spotify_playlist(spotify_client, url: str) -> list[str]:
    try:
        playlist_id = url.split('playlist/')[1].split('?')[0]
        results = spotify_client.playlist_tracks(playlist_id)
        tracks = []
        while results:
            for item in results['items']:
                if item and 'track' in item and item['track']:
                    track = item['track']
                    if track['name'] and track['artists']:
                        artist_name = track['artists'][0]['name']
                        track_name = track['name']
                        search_query = f"{track_name} {artist_name} audio"
                        tracks.append(search_query)
            if results['next']:
                results = spotify_client.next(results)
            else:
                break
        return tracks
    except Exception as e:
        print(f"Spotify 播放清單處理錯誤: {e}")
        return []
    
@client.tree.command(name="nowplaymsg", description="開啟/關閉目前歌曲的提示訊息")
async def nowplaymsg(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    if guild_id not in client.show_now_song:
        client.show_now_song[guild_id] = True
    client.show_now_song[guild_id] = not client.show_now_song[guild_id]
    status = "開啟" if client.show_now_song[guild_id] else "關閉"
    if client.show_now_song[guild_id]:
        embed_color = EMBED_COLORS['success']
        embed = discord.Embed(
            title="⚙️ 播放提示設置",
            description=f"下一首歌曲提示已{status}",
            color=embed_color
        )
        embed.add_field(
            name="目前設定", 
            value="將在播放前發送目前歌曲的提示訊息",
            inline=False
        )
        embed.set_footer(text="✅預設開啟")
    else:
        embed_color = EMBED_COLORS['error']
        embed = discord.Embed(
            title="⚙️ 播放提示設置",
            description=f"下一首歌曲提示已{status}",
            color=embed_color
        )
        embed.add_field(
            name="目前設定",
            value="已關閉發送目前歌曲的提示訊息",
            inline=False
        )
        embed.set_footer(text="✅預設開啟")
    await interaction.response.send_message(embed=embed)
@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel is None or after.channel == before.channel:
        return
    if before.channel and client.user in before.channel.members:
        channel = before.channel
        if channel.id == 1287276156994981903:
            return
        if len(channel.members) == 1:
            guild_id = channel.guild.id
            channel_id = channel.id
            client.empty_channel_timers[channel_id] = {
                'start_time': datetime.datetime.now(),
                'warned': False
            }
            await asyncio.sleep(45)
            if (channel_id in client.empty_channel_timers and 
                len(channel.members) == 1 and 
                client.user in channel.members):
                if not client.empty_channel_timers[channel_id]['warned']:
                    warn_embed = discord.Embed(
                        title="⚠️ 即將自動離開",
                        description=f"頻道內只剩機器人\n將在 15 秒後自動離開",
                        color=EMBED_COLORS['warning']
                    )
                    await send_message_to_last_channel(guild_id, embed=warn_embed)
                    client.empty_channel_timers[channel_id]['warned'] = True
                await asyncio.sleep(15)
                if (channel_id in client.empty_channel_timers and 
                    len(channel.members) == 1 and 
                    client.user in channel.members):
                    vc = channel.guild.voice_client
                    if vc:
                        await vc.disconnect()
                        bye_embed = discord.Embed(
                        title="👋 掰",
                        description=f"",
                        color=EMBED_COLORS['success']
                        )
                        await send_message_to_last_channel(guild_id, embed=bye_embed)
                        if guild_id in client.queues:
                            client.queues[guild_id].clear()
                        await update_presence()
                    if channel_id in client.empty_channel_timers:
                        del client.empty_channel_timers[channel_id]
        else:
            if channel.id in client.empty_channel_timers:
                del client.empty_channel_timers[channel.id]
async def process_spotify_album(spotify_client, url: str) -> list[str]:
    try:
        album_id = url.split('album/')[1].split('?')[0]
        results = spotify_client.album_tracks(album_id)
        tracks = []
        for track in results['items']:
            if track['name'] and track['artists']:
                artist_name = track['artists'][0]['name']
                track_name = track['name']
                search_query = f"{track_name} {artist_name}".replace("&", "and")
                tracks.append(search_query)
        return tracks
    except Exception as e:
        print(f"Spotify 專輯處理錯誤: {e}")
        return []
async def process_youtube_playlist(url: str) -> list[str]:
    try:
        if 'list=' not in url:
            return []
        playlist_id = url.split('list=')[1].split('&')[0]
        playlist_url = f"https://youtube.com/playlist?list={playlist_id}"
        try:
            playlist = await wavelink.Playable.search(playlist_url)
            if isinstance(playlist, wavelink.Playlist):
                return [track.uri for track in playlist.tracks]
            return [track.uri for track in playlist if hasattr(track, 'uri')]
        except Exception as e:
            print(f"播放清單搜尋錯誤: {e}")
            return []
    except Exception as e:
        print(f"YouTube 播放清單處理錯誤: {e}")
        return []
async def send_playlist_results(interaction: discord.Interaction, added_songs: list, failed_songs: list, playlist_name: str):
    embed = discord.Embed(
        title=f"✅ {playlist_name} 處理完成",
        color=EMBED_COLORS['success']
    )
    if added_songs:
        total_duration = sum(song.duration for song in added_songs)
        minutes = total_duration // 60
        hours = minutes // 60
        minutes %= 60
        duration_text = f"{hours}小時{minutes}分鐘" if hours > 0 else f"{minutes}分鐘"
        embed.add_field(
            name="✅ 已添加歌曲",
            value=f"成功添加 {len(added_songs)} 首歌曲\n總時長：{duration_text}",
            inline=False
        )
    if failed_songs:
        failed_per_page = 10
        total_failed = len(failed_songs)
        total_pages = (total_failed + failed_per_page - 1) // failed_per_page
        embed.add_field(
            name="❌ 處理失敗",
            value=f"無法添加 {total_failed} 首歌曲 請到上則訊息查看",
            inline=False
        )
        await interaction.followup.send(embed=embed)
        if total_failed > failed_per_page:
            for page in range(total_pages):
                start_idx = page * failed_per_page
                end_idx = min(start_idx + failed_per_page, total_failed)
                failed_embed = discord.Embed(
                    title=f"❌ 處理失敗歌曲清單 ({page+1}/{total_pages})",
                    description="\n".join(
                        f"{i+1}. {song}" 
                        for i, song in enumerate(failed_songs[start_idx:end_idx], start=start_idx)
                    ),
                    color=EMBED_COLORS['error']
                )
                await interaction.followup.send(embed=failed_embed)
        elif failed_songs:  # 如果失敗歌曲少於10首，直接顯示
            failed_embed = discord.Embed(
                title="❌ 處理失敗歌曲清單",
                description="\n".join(f"{i+1}. {song}" for i, song in enumerate(failed_songs)),
                color=EMBED_COLORS['error']
            )
            await interaction.edit_original_response(embed=failed_embed)
    else:
        await interaction.edit_original_response(embed=embed)
async def process_playlist(interaction: discord.Interaction, search_queries: list[str], playlist_name: str):
    try:
        guild_id = interaction.guild_id
        added_songs = []
        failed_songs = []
        progress_embed = discord.Embed(
            title="⏳ 正在處理播放清單",
            description=f"正在處理 {playlist_name}\n共 {len(search_queries)} 首歌曲",
            color=EMBED_COLORS['info']
        )
        progress_message = await interaction.followup.send(embed=progress_embed)
        original_url = search_queries[0] if search_queries else ""
        platform = get_platform(original_url)
        first_song_played = False  # 新增旗標
        for index, query in enumerate(search_queries):
            try:
                tracks = await wavelink.Playable.search(query)
                if tracks:
                    track = tracks[0]
                    song = Song(
                        url=track.uri,
                        title=track.title,
                        duration=int(track.length // 1000),
                        thumbnail=track.artwork,
                        requester=interaction.user,
                        platform=platform  # 使用原始平台
                    )
                    client.queues[guild_id].append(song)
                    added_songs.append(song)
                    if not first_song_played and not interaction.guild.voice_client.playing:
                        await play_next(interaction.guild, interaction.guild.voice_client)
                        first_song_played = True
                else:
                    failed_songs.append(query)
            except Exception as e:
                print(f"處理歌曲時發生錯誤：{str(e)}")
                failed_songs.append(query)
            if (index + 1) % 20 == 0 or index == len(search_queries) - 1:
                progress_embed.description = f"正在處理 {playlist_name}\n已完成 {index + 1}/{len(search_queries)} 首歌曲"
                await progress_message.edit(embed=progress_embed)
            await asyncio.sleep(0.1)  # 建議加一點延遲，避免大量請求
        await send_playlist_results(interaction, added_songs, failed_songs, playlist_name)
    except Exception as e:
        print(f"處理播放清單時發生錯誤：{str(e)}")
        error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}")
        await interaction.followup.send(embed=error_embed)
def extract_video_id(url: str) -> Optional[str]:
    try:
        if 'youtube.com/watch?v=' in url:
            return url.split('watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        return None
    except:
        return None
async def get_recommendations(current_song: Song) -> Optional[Song]:
    try:
        search_query = f"{current_song.title} {current_song.artist}" if hasattr(current_song, "artist") else current_song.title
        tracks = await wavelink.Playable.search(search_query)
        tracks = [t for t in tracks if t.uri != current_song.url]
        if tracks:
            track = random.choice(tracks)  # 隨機選擇一首
            return Song(
                url=track.uri,
                title=track.title,
                duration=int(track.length // 1000),
                thumbnail=track.artwork,
                requester=current_song.requester,
                platform='youtube'
            )
    except Exception as e:
        print(f"獲取推薦時發生錯誤: {e}")
    return None
async def check_voice_state_and_respond(interaction: discord.Interaction) -> bool:
    if not interaction.user.voice:
        embed = discord.Embed(
            title="❌ 錯誤",
            description="請先加入語音頻道",
            color=EMBED_COLORS['error']
        )
        await interaction.followup.send(embed=embed)
        return False
    return True
client.run(config["discord_bot_token"])
