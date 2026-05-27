import discord
from discord import app_commands
from discord.ext import commands
import wavelink
from collections import deque

from service.play import play_next, update_activity_time, Song  
from service.playlist import process_playlist, process_spotify_track, process_spotify_album, get_platform, process_spotify_playlist, process_youtube_playlist
from service.embed import check_voice_state_and_respond, create_song_embed, create_music_embed, create_error_embed, start_auto_update, EMBED_COLORS
from service.Lavalink import LavalinkPlayerCompat
from service.view import MusicControlView


class Musicplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_client(self):
        return self.bot

    py = app_commands.Group(name="音樂", description="音樂相關指令")
    #==播放音樂==
    @py.command(name="播放", description="播放音樂")
    async def play(self, interaction: discord.Interaction, query: str):
        client = self.get_client()
        await update_activity_time(interaction.guild_id, client)
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
                            vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=LavalinkPlayerCompat)
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
                    await process_playlist(interaction=interaction, search_queries=search_queries, playlist_name="播放清單")
                except Exception as e:
                    print(f"處理播放清單時發生錯誤: {e}")
                    error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}", client.config)
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
                            vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=LavalinkPlayerCompat)
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
                                await play_next(guild=interaction.guild, vc=vc, client=client)
                                current_song = client.current_songs.get(guild_id)
                                if current_song:
                                    view = MusicControlView(current_song, vc, guild_id, client)
                                    message = await interaction.followup.send(embed=None, view=view)
                                    await start_auto_update(guild_id, vc, message, view)
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
    #==暫停音樂==
    @py.command(name="暫停", description="暫停音樂")
    async def pause(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        if not interaction.guild.voice_client:
            embed = discord.Embed(
                title="❌ 無法暫停",
                description="機器人不在語音頻道中",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc.playing:
            embed = discord.Embed(
                title="❌ 無法暫停",
                description="目前沒有播放任何歌曲",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        try:
            if vc.paused:
                embed = discord.Embed(
                    title="⚠️ 已經暫停",
                    description="音樂已經處於暫停狀態",
                    color=EMBED_COLORS['warning']
                )
                await interaction.followup.send(embed=embed)
                return
            await vc.pause(True)
            embed = discord.Embed(
                title="⏸️ 已暫停",
                description="音樂已暫停播放",
                color=EMBED_COLORS['success']
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"暫停時發生錯誤：{e}")
            embed = create_error_embed(f"暫停時時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=embed)
    #==繼續播放==
    @py.command(name="繼續", description="繼續播放")
    async def resume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        if not interaction.guild.voice_client:
            embed = discord.Embed(
                title="❌ 無法繼續播放",
                description="機器人不在語音頻道中",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc.playing:
            embed = discord.Embed(
                title="❌ 無法繼續播放",
                description="目前沒有播放任何歌曲",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        try:
            if not vc.paused:
                embed = discord.Embed(
                    title="⚠️ 已在播放中",
                    description="音樂已經在播放中",
                    color=EMBED_COLORS['warning']
                )
                await interaction.followup.send(embed=embed)
                return
            await vc.pause(False)
            embed = discord.Embed(
                title="▶️ 繼續播放",
                description="音樂已繼續播放",
                color=EMBED_COLORS['success']
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"繼續播放時發生錯誤：{e}")
            embed = create_error_embed(f"繼續播放時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=embed)
    #==跳過音樂==
    @py.command(name="跳過", description="跳過目前的歌曲")
    async def skip(self, interaction: discord.Interaction):
        client = self.get_client()
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        vc: wavelink.Player = interaction.guild.voice_client
        guild_id = interaction.guild_id
        if not vc.playing:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
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
        await interaction.followup.send(embed=embed)
        await vc.stop()
    #==音樂音量==
    @py.command(name="音量", description="調整音樂音量")
    async def volume(self, interaction: discord.Interaction, vol: int):
        client = self.get_client()
        await interaction.response.defer()
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc:
            embed = discord.Embed(
                title="❌ 機器人未在語音頻道",
                description="請先使用 /play 播放音樂",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        if vol < 0 or vol > 150:
            embed = discord.Embed(
                title="❌ 音量範圍錯誤",
                description="音量必須在 0 到 150 之間",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        await vc.set_volume(vol)
        client.guild_volumes[guild_id] = vol
        embed = discord.Embed(
            title="🔊 音量已調整",
            description=f"音量已設定為 {vol}",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed)
    #==音樂控制器==
    @py.command(name="控制器", description="叫出音樂控制器")
    async def musiccontrol(self, interaction: discord.Interaction):
        client = self.get_client()
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        song = client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, client)
        message = await interaction.followup.send(embed=None, view=view)
        await start_auto_update(guild_id, vc, message, view)
    #==循環模式==
    @py.command(name="循環", description="切換循環播放模式")
    async def loop(self, interaction: discord.Interaction):
        client = self.get_client()
        await interaction.response.defer()
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
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Musicplay(bot))