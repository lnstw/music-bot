import discord
from discord import app_commands
from discord.ext import commands
from core.embed import check_voice_state_and_respond, create_song_embed, create_error_embed, EMBED_COLORS, start_auto_update
from core.playlist import process_playlist, process_spotify_track, process_spotify_album, get_platform, process_spotify_playlist, process_youtube_playlist
from core.view import MusicControlView
from core.player import CustomPlayer
from core.config import config, spotify
import lava_lyra
import logging


class Musicplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_client(self):
        return self.bot

    py = app_commands.Group(name="音樂", description="音樂相關指令")
    #==播放音樂==
    @py.command(name="播放", description="播放音樂")
    async def play(self, interaction: discord.Interaction, query: str):
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
                if not interaction.guild.voice_client:
                    try:
                        player: CustomPlayer = await interaction.user.voice.channel.connect(cls=CustomPlayer)
                    except Exception as e:
                        error_embed = create_error_embed(f"無法連接語音頻道：{str(e)}")
                        await interaction.followup.send(embed=error_embed)
                        return
                else:
                    player: CustomPlayer = interaction.guild.voice_client
                platform = get_platform(query)
                search_queries = []
                try:
                    if platform == 'spotify':
                        if 'playlist' in query.lower():
                            search_queries = await process_spotify_playlist(spotify, query)
                        elif 'album' in query.lower():
                            search_queries = await process_spotify_album(spotify, query)
                    elif platform == 'youtube':
                        if 'list=' in query:
                            search_queries = await process_youtube_playlist(player, query)
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
                            player: CustomPlayer = await interaction.user.voice.channel.connect(cls=CustomPlayer)
                        except Exception as e:
                            error_embed = create_error_embed(f"無法連接語音頻道：{str(e)}")
                            await interaction.followup.send(embed=error_embed)
                            return
                    else:
                        player: CustomPlayer = interaction.guild.voice_client
                    player._last_channel = interaction.channel
                    await process_playlist(interaction=interaction, search_queries=search_queries, playlist_name="播放清單")
                except Exception as e:
                    logging.error(f"處理播放清單時發生錯誤: {e}")
                    error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}", config)
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
                                search_queries = await process_spotify_playlist(spotify, query)
                            elif 'album' in query.lower():
                                search_queries = await process_spotify_album(spotify, query)
                            else:
                                search_query = await process_spotify_track(spotify, query)
                                if search_query:
                                    search_queries = [search_query]
                        elif platform == 'youtube':
                            if 'playlist' in query.lower() or 'list=' in query:
                                if interaction.guild.voice_client:
                                    player: CustomPlayer = interaction.guild.voice_client
                                else:
                                    player: CustomPlayer = await interaction.user.voice.channel.connect(cls=CustomPlayer)
                                search_queries = await process_youtube_playlist(player, query)
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
                        logging.error(f"URL 處理錯誤: {e}")
                        embed = discord.Embed(
                            title="❌ 無法處理連結",
                            description="處理連結時發生錯誤，請嘗試其他連結或直接搜尋歌名",
                            color=EMBED_COLORS['error']
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    if not interaction.guild.voice_client:
                        try:
                            player: CustomPlayer = await interaction.user.voice.channel.connect(cls=CustomPlayer)
                        except Exception as e:
                            error_embed = create_error_embed(f"無法連接語音頻道：{str(e)}")
                            await interaction.followup.send(embed=error_embed)
                            return
                    else:
                        player: CustomPlayer = interaction.guild.voice_client
                    player._last_channel = interaction.channel
                    await player.initialize_volume()
                    try:
                        tracks = await player.get_tracks(search_queries[0])
                        if tracks:
                            track = tracks[0]
                            track.requester = interaction.user
                            player.queue.put(track)
                            embed = create_song_embed(track, player.queue.count)
                            await interaction.followup.send(embed=embed)
                            if not player.is_playing:
                                await player.play_next()
                                current_song = player.current
                                if current_song:
                                    view = MusicControlView(current_song, player)
                                    message = await interaction.followup.send(view=view)
                                    await start_auto_update(interaction.guild_id, player, message)
                        else:
                            embed = discord.Embed(
                                title="❌ 無法找到歌曲",
                                description="請嘗試其他連結或直接搜尋歌名",
                                color=EMBED_COLORS['error']
                            )
                            await interaction.followup.send(embed=embed)
                    except Exception as e:
                        logging.error(f"播放歌曲時發生錯誤：{str(e)}")
                        error_embed = create_error_embed(f"播放歌曲時發生錯誤：{str(e)}")
                        await interaction.followup.send(embed=error_embed)
                except Exception as e:
                    logging.error(f"播放指令發生錯誤：{str(e)}")
                    error_embed = create_error_embed(f"播放指令發生錯誤：{str(e)}")
                    await interaction.followup.send(embed=error_embed)
        except Exception as e:
                    logging.error(f"播放指令發生錯誤：{str(e)}")
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
        player: CustomPlayer = interaction.guild.voice_client
        if not player.is_playing:
            embed = discord.Embed(
                title="❌ 無法暫停",
                description="目前沒有播放任何歌曲",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        try:
            if player.is_paused:
                embed = discord.Embed(
                    title="⚠️ 已經暫停",
                    description="音樂已經處於暫停狀態",
                    color=EMBED_COLORS['warning']
                )
                await interaction.followup.send(embed=embed)
                return
            await player.set_pause(True)
            embed = discord.Embed(
                title="⏸️ 已暫停",
                description="音樂已暫停播放",
                color=EMBED_COLORS['success']
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logging.error(f"暫停時發生錯誤：{e}")
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
        player: CustomPlayer = interaction.guild.voice_client
        if not player.is_playing:
            embed = discord.Embed(
                title="❌ 無法繼續播放",
                description="目前沒有播放任何歌曲",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        try:
            if not player.is_paused:
                embed = discord.Embed(
                    title="⚠️ 已在播放中",
                    description="音樂已經在播放中",
                    color=EMBED_COLORS['warning']
                )
                await interaction.followup.send(embed=embed)
                return
            await player.set_pause(False)
            embed = discord.Embed(
                title="▶️ 繼續播放",
                description="音樂已繼續播放",
                color=EMBED_COLORS['success']
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logging.error(f"繼續播放時發生錯誤：{e}")
            embed = create_error_embed(f"繼續播放時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=embed)
    #==跳過音樂==
    @py.command(name="跳過", description="跳過目前的歌曲")
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return    
        player: CustomPlayer = interaction.guild.voice_client
        if not player.is_playing and not player.current:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        queue_list = player.queue.get_queue() if hasattr(player.queue, 'get_queue') else list(player.queue)
        next_track = None
        if queue_list:
            if player.current and queue_list[0].uri == player.current.uri:
                if len(queue_list) > 1:
                    next_track = queue_list[1]
            else:
                next_track = queue_list[0]
        if not next_track and getattr(player.queue, 'is_looping', False):
            next_track = player.current
        embed = discord.Embed(
            title="⏭️ 已跳過當前歌曲",
            color=EMBED_COLORS['success']
        )
        if next_track:
            embed.add_field(
                name="即將播放",
                value=f"[{next_track.title}]({next_track.uri})",
                inline=False
            )
        else:
            embed.description = "佇列中已無其他歌曲。"
        await interaction.followup.send(embed=embed)
        if hasattr(player, 'skip'):
            await player.skip()
        else:
            await player.stop()
    #==音樂音量==
    @py.command(name="音量", description="調整音樂音量")
    async def volume(self, interaction: discord.Interaction, vol: int):
        await interaction.response.defer()
        player: CustomPlayer = interaction.guild.voice_client
        if not player:
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
        await player.set_volume(vol)
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
        player: CustomPlayer = interaction.guild.voice_client
        if not player or not player.is_playing:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        song = player.current
        view = MusicControlView(song, player)
        message = await interaction.followup.send(view=view)
        await start_auto_update(interaction.guild_id, player, message)
    #==循環模式==
    @py.command(name="循環", description="切換循環播放模式")
    async def loop(self, interaction: discord.Interaction):
        client = self.get_client()
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        player: CustomPlayer = interaction.guild.voice_client
        if not player or not player.is_playing:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        player.queue.set_loop_mode(player.queue.disable_loop() if player.queue.loop_mode else player.queue.set_loop_mode(lava_lyra.LoopMode.QUEUE)) 
        status = "開啟" if player.queue.is_looping else "關閉"
        embed = discord.Embed(
            title="🔄 循環播放設置",
            description=f"循環播放已{status}",
            color=EMBED_COLORS['success']
        )
        if player.queue.is_looping:
            total_songs = player.queue.count
            embed.add_field(
                name="循環清單",
                value=f"目前共有 {total_songs} 首歌曲在循環播放中",
                inline=False
            )
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Musicplay(bot))