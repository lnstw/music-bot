import discord
from discord import app_commands
import wavelink
from collections import deque
import asyncio
import random
from io import BytesIO
import datetime
from datetime import timedelta
import aiohttp
from core import client, config, Song, EMBED_COLORS, RefreshButton, opselect_view, config, get_dominant_color
from service.play import play_next
from service.embed import create_song_embed, create_error_embed, check_voice_state_and_respond, create_music_embed, start_auto_update
from service.channel import send_message_to_last_channel
from service.playlist import process_spotify_track, process_spotify_album, process_youtube_playlist, get_platform, process_spotify_playlist, process_playlist
from service.view import MusicControlView, QueuePaginator
async def update_activity_time(guild_id: int):
    client.last_activity[guild_id] = datetime.datetime.now()

@client.tree.command(name="play", description="播放音樂")
async def play(interaction: discord.Interaction, query: str):
    await update_activity_time(interaction.guild_id)
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
                await process_playlist(interaction=interaction, search_queries=search_queries, playlist_name="播放清單")
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
                            await play_next(guild=interaction.guild, vc=vc)
                            current_song = client.current_songs.get(guild_id)
                            if current_song:
                                embed = create_music_embed(current_song, vc, guild_id)
                                view = MusicControlView()
                                message = await interaction.followup.send(embed=embed, view=view)
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
            await play_next(guild=guild, vc=payload.player)
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

@client.tree.command(name="pause", description="暫停播放")
async def pause(interaction: discord.Interaction):
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

@client.tree.command(name="resume", description="繼續播放")
async def resume(interaction: discord.Interaction):
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

@client.tree.command(name="stop", description="停止播放並清空播放清單")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await check_voice_state_and_respond(interaction):
            return
    if not interaction.guild.voice_client:
        await interaction.followup.send("❌ 沒有歌曲正在播放！")
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
        client.loop_mode[guild_id] = False
    if guild_id in client.auto_recommend:
        client.auto_recommend[guild_id] = False
    vc.queue.clear()
    await client.update_presence()
    embed = discord.Embed(
        title="⏹️ 已停止播放",
        description="已清空播放清單並關閉循環模式",
        color=EMBED_COLORS['success']
    )
    if guild_id in client.auto_recommend and client.auto_recommend[guild_id]:
        embed.set_footer(text="自動推薦功能仍然開啟")
    await interaction.followup.send(embed=embed)

@client.tree.command(name="skip", description="跳過當前歌曲")
async def skip(interaction: discord.Interaction):
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

@client.tree.command(name="volume", description="調整音量")
@app_commands.describe(volume="音量大小 (0-150)")
async def volume(interaction: discord.Interaction, volume: int):
    try:
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 機器人不在語音頻道中！")
            return
        if not 0 <= volume <= 150:
            await interaction.followup.send("❌ 音量必須在 0-150 之間！")
            return
        client.default_volume = volume
        vc: wavelink.Player = interaction.guild.voice_client
        await vc.set_volume(volume)
        await interaction.followup.send(f"🔊 音量已設定為 {volume}%")
    except Exception as e:
        print(f"調整音量時發生錯誤：{str(e)}")
        error_embed = create_error_embed(f"調整音量時發生錯誤：{str(e)}")
        await interaction.followup.send(embed=error_embed)

@client.tree.command(name="loop", description="切換循環播放模式")
async def loop(interaction: discord.Interaction):
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

@client.tree.command(name="shuffle", description="隨機播放清單")
async def shuffle(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if guild_id not in client.queues or not client.queues[guild_id]:
        await interaction.followup.send("❌ 播放清單是空的！")
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
    await interaction.followup.send(embed=embed)


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
        "play": "播放音樂 (支援 YouTube/Spotify)",
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
    await interaction.response.defer()
    if not interaction.user.guild_permissions.move_members:
        if not await check_voice_state_and_respond(interaction):
            return
    else:
        pass
    if not interaction.guild.voice_client:
        await interaction.followup.send("❌ 機器人不在語音頻道中！")
        return
    vc: wavelink.Player = interaction.guild.voice_client
    await vc.disconnect()
    guild_id = interaction.guild_id
    if guild_id in client.queues:
        client.queues[guild_id].clear()
    if guild_id in client.current_songs:
        del client.current_songs[guild_id]
    await interaction.followup.send("👋 已離開語音頻道")
    await client.update_presence()

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
        volume = client.default_volume
        auto_recommend_status = client.auto_recommend.get(guild_id, False)
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
                await asyncio.sleep(1)
            except Exception as e:
                print(f"斷開連接時發生錯誤：{e}")
        try:
            vc: wavelink.Player = await current_channel.connect(cls=wavelink.Player)
            await vc.set_volume(volume)
            if current_queue:
                client.queues[guild_id] = deque(current_queue)
            if current_song:
                client.current_songs[guild_id] = current_song
            client.loop_mode[guild_id] = loop_status
            client.auto_recommend[guild_id] = auto_recommend_status
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
                    await play_next(guild=interaction.guild, vc=vc)
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
    await interaction.response.defer()
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
    await interaction.followup.send(embed=embed)

@client.tree.command(name="remove", description="從播放清單中移除指定歌曲")
@app_commands.describe(position="要移除的歌曲位置")
async def remove(interaction: discord.Interaction, position: int):
    await interaction.response.defer()
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if guild_id not in client.queues or not client.queues[guild_id]:
        await interaction.followup.send("❌ 播放清單是空的！")
        return
    queue_list = list(client.queues[guild_id])
    if position < 1 or position > len(queue_list):
        await interaction.followup.send("❌ 無效的歌曲位置！")
        return
    if client.loop_mode.get(guild_id, False):
        current_song = client.current_songs.get(guild_id)
        if current_song == queue_list[position-1]:
            await interaction.followup.send("❌ 無法移除當前播放的歌曲！")
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
    await interaction.followup.send(embed=embed)

@client.tree.command(name="clear", description="清空播放清單")
async def clear(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await check_voice_state_and_respond(interaction):
            return
    guild_id = interaction.guild_id
    if not interaction.guild.voice_client:
        await interaction.followup.send("❌ 機器人不在語音頻道中！")
        return
    if guild_id not in client.queues:
        client.queues[guild_id] = deque()
    if not client.queues[guild_id]:
        await interaction.followup.send("❌ 播放清單已經是空的！")
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
            del client.current_songs[guild_id]
        if guild_id in client.loop_mode:
            client.loop_mode[guild_id] = False
        embed = discord.Embed(
            title="🗑️ 已清空播放清單",
            description="已清空所有歌曲並關閉循環模式",
            color=EMBED_COLORS['success']
        )
    await interaction.followup.send(embed=embed)

@client.tree.command(name="playnext", description="將歌曲插入到播放清單的下一個位置")
async def playnext(interaction: discord.Interaction, query: str):
    await update_activity_time(interaction.guild_id)
    try:
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        if guild_id not in client.queues or not client.queues[guild_id]:
            commands = await client.tree.fetch_commands()
            cmd_dict = {cmd.name: cmd.id for cmd in commands}
            cmd_id = cmd_dict.get("play", "00")
            error_embed = discord.Embed(title="",description=f"請先使用</play:{cmd_id}>",color=EMBED_COLORS["error"])
            await interaction.followup.send(embed=error_embed)
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

        if guild_id not in client.queues:
            client.queues[guild_id] = deque()
        client.last_channels[guild_id] = interaction.channel_id

        # 🔍 判斷是否為播放清單
        is_playlist = False
        if 'spotify.com' in query:
            if 'playlist' in query or 'album' in query:
                is_playlist = True
        elif 'youtube.com' in query or 'youtu.be' in query:
            if 'list=' in query:
                is_playlist = True

        platform = get_platform(query)

        if is_playlist:
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

                await process_playlist(
                    interaction=interaction,
                    search_queries=search_queries,
                    playlist_name="插播播放清單",
                    insert_next=True
                )
                return
            except Exception as e:
                print(f"處理播放清單時發生錯誤: {e}")
                error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}")
                await interaction.followup.send(embed=error_embed)
                return

        search_queries = []
        try:
            if platform == 'spotify':
                if 'track' in query.lower():
                    search_query = await process_spotify_track(client.spotify, query)
                    if search_query:
                        search_queries = [search_query]
                else:
                    embed = discord.Embed(
                        title="⚠️ 不支援的功能",
                        description="插播功能不支援 Spotify 播放清單或專輯連結",
                        color=EMBED_COLORS['warning']
                    )
                    await interaction.followup.send(embed=embed)
                    return
            elif platform == 'youtube':
                if 'list=' in query:
                    embed = discord.Embed(
                        title="⚠️ 不支援的功能",
                        description="插播功能不支援 YouTube 播放清單連結",
                        color=EMBED_COLORS['warning']
                    )
                    await interaction.followup.send(embed=embed)
                    return
                else:
                    search_queries = [query]
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
                    insert_pos = queue_list.index(current_song) + 1 if current_song in queue_list else 0
                else:
                    insert_pos = 0
                queue_list.insert(insert_pos, song)
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
                    await play_next(guild=interaction.guild, vc=vc)
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

@client.tree.command(name="隨機圖", description="可以隨機給你一張圖片")
async def img(interaction: discord.Interaction):
    await interaction.response.defer()
    start_time = datetime.datetime.now()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.redbean0721.com/api/img?type=json") as api_response:
            end_time = datetime.datetime.now()
            if api_response.status != 200:
                await interaction.followup.send("無法獲取圖片，請稍後再試。")
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
            await interaction.followup.send(embed=embed, view=view, file=file)
        

@client.tree.command(name="nowplaymsg", description="開啟/關閉目前歌曲的提示訊息")
async def nowplaymsg(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    if guild_id not in client.show_now_song:
        client.show_now_song[guild_id] = False
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
                    await send_message_to_last_channel(guild_id=guild_id, embed=warn_embed)
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
                        await send_message_to_last_channel(guild_id=guild_id, embed=bye_embed)
                        if guild_id in client.queues:
                            client.queues[guild_id].clear()
                        await client.update_presence()
                    if channel_id in client.empty_channel_timers:
                        del client.empty_channel_timers[channel_id]
        else:
            if channel.id in client.empty_channel_timers:
                del client.empty_channel_timers[channel.id]

@client.tree.command(name="開發者命令", description="開發者命令")
@app_commands.default_permissions(manage_roles=True)
async def 開發者命令(interaction: discord.Interaction):
    if interaction.user.id != int(config["discord_user_id"]):
        await interaction.response.send_message("❌ 你沒有權限使用此指令", ephemeral=True)
        return
    view = opselect_view()
    await interaction.response.send_message("請選擇功能", view=view, ephemeral=True)


@client.tree.command(name="musiccontrol", description="音樂控制器")
async def musiccontrol(interaction: discord.Interaction):
    await interaction.response.defer()
    if not await check_voice_state_and_respond(interaction):
        return
    guild_id = interaction.guild_id
    vc: wavelink.Player = interaction.guild.voice_client
    if not vc or not vc.playing:
        await interaction.followup.send("❌ 沒有歌曲正在播放！")
        return
    song = client.current_songs.get(guild_id)
    embed = create_music_embed(song, vc, guild_id)
    view = MusicControlView()
    message = await interaction.followup.send(embed=embed, view=view)
    await start_auto_update(guild_id, vc, message, view)

client.run(config["discord_bot_token"])