import asyncio
import discord
from typing import Optional
from urllib.parse import urlparse
import lava_lyra
import logging
from core.embed import create_error_embed, EMBED_COLORS
from core.view import MusicControlView
from core.player import CustomPlayer
import logging

_client = None
def set_client_ref(client):
    global _client
    _client = client

async def process_spotify_track(spotify_client, url: str) -> Optional[str]:
    try:
        track_id = url.split('track/')[1].split('?')[0]
        track = spotify_client.track(track_id)
        artist_name = track['artists'][0]['name']
        track_name = track['name']
        return f"{track_name} {artist_name} audio"
    except Exception as e:
        logging.error(f"Spotify 處理錯誤: {e}")
        return None
    
def get_platform(url: str) -> str:
    try:
        domain = urlparse(url).netloc.lower()
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        elif 'spotify.com' in domain:
            return 'spotify'
    except:
        pass
    return 'youtube'

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
        logging.error(f"Spotify 專輯處理錯誤: {e}")
        return []
    
async def process_youtube_playlist(player: CustomPlayer, url: str) -> list[str]:
    try:
        if 'list=' not in url:
            return []
        playlist_id = url.split('list=')[1].split('&')[0]
        playlist_url = f"https://youtube.com/playlist?list={playlist_id}"
        try:
            playlist = await player.get_tracks(playlist_url)
            if isinstance(playlist, lava_lyra.Playlist):
                return [track.uri for track in playlist.tracks]
            return [track.uri for track in playlist if hasattr(track, 'uri')]
        except Exception as e:
            logging.error(f"播放清單搜尋錯誤: {e}")
            return []
    except Exception as e:
        logging.error(f"YouTube 播放清單處理錯誤: {e}")
        return []

async def send_playlist_results(interaction: discord.Interaction, added_tracklist: list[lava_lyra.Track], failed_tracklist: list, playlist_name: str):
    embed = discord.Embed(
        title=f"✅ {playlist_name} 處理完成",
        color=EMBED_COLORS['success']
    )
    if added_tracklist:
        total_duration_ms = sum(track.length for track in added_tracklist)
        total_duration = int(total_duration_ms / 1000)
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        duration_text = f"{hours}小時{minutes}分鐘" if hours > 0 else f"{minutes}分鐘"
        embed.add_field(
            name="✅ 已添加歌曲",
            value=f"成功添加 {len(added_tracklist)} 首歌曲\n總時長：{duration_text}",
            inline=False
        )
        await interaction.edit_original_response(embed=embed)

        guild_id = interaction.guild_id
        vc: CustomPlayer = interaction.guild.voice_client
        track = vc.current
        if track and vc and vc.is_playing:
            view = MusicControlView(track, vc)
            message = await interaction.followup.send(view=view, silent=True)
            from core.embed import start_auto_update
            await start_auto_update(interaction.guild_id, vc, message)
        else:
            logging.error(f"[send_playlist_results] 無法取得目前歌曲或未在播放 (song={track}, vc.playing={vc.is_playing if vc else False})")
    if failed_tracklist:
        failed_per_page = 10
        total_failed = len(failed_tracklist)
        total_pages = (total_failed + failed_per_page - 1) // failed_per_page
        embed.add_field(
            name="❌ 處理失敗",
            value=f"無法添加 {total_failed} 首歌曲 請到上則訊息查看",
            inline=False
        )
        await interaction.followup.send(embed=embed,silent=True)
        if total_failed > failed_per_page:
            for page in range(total_pages):
                start_idx = page * failed_per_page
                end_idx = min(start_idx + failed_per_page, total_failed)
                failed_embed = discord.Embed(
                    title=f"❌ 處理失敗歌曲清單 ({page+1}/{total_pages})",
                    description="\n".join(
                        f"{i+1}. {song}" 
                        for i, song in enumerate(failed_tracklist[start_idx:end_idx], start=start_idx)
                    ),
                    color=EMBED_COLORS['error']
                )
                await interaction.followup.send(embed=failed_embed,silent=True)
        elif failed_tracklist:
            failed_embed = discord.Embed(
                title="❌ 處理失敗歌曲清單",
                description="\n".join(f"{i+1}. {song}" for i, song in enumerate(failed_tracklist)),
                color=EMBED_COLORS['error']
            )
            await interaction.edit_original_response(embed=failed_embed)
    else:
        await interaction.edit_original_response(embed=embed)

async def process_playlist(
    interaction: discord.Interaction,
    search_queries: list[str],
    playlist_name: str,
    insert_next: bool = False
):
    try:
        guild_id = interaction.guild_id
        added_songs = []
        failed_songs = []
        first_song_added = False
        progress_embed = discord.Embed(
            title="⏳ 正在處理播放清單",
            description=f"正在處理 {playlist_name}\n共 {len(search_queries)} 首歌曲",
            color=EMBED_COLORS['info']
        )
        progress_message = await interaction.followup.send(embed=progress_embed)
        original_url = search_queries[0] if search_queries else ""
        platform = get_platform(original_url)
        queries = reversed(search_queries) if insert_next else search_queries
        player: CustomPlayer = interaction.guild.voice_client
        queue_list = player.queue.get_queue()
        for index, query in enumerate(queries):
            try:
                tracks = await player.get_tracks(query)
                if tracks and tracks[0] is not None:
                    track = tracks[0]
                    if insert_next:
                        if player and player.queue.is_looping:
                            current_song = player.current
                            insert_pos = queue_list.index(current_song) + 1 if current_song in queue_list else 0
                        else:
                            insert_pos = 0
                        player.queue.put_at_index(insert_pos, track)
                    else:
                        player.queue.put(track)
                    added_songs.append(track)
                    if not first_song_added and not player.is_playing:
                        if player:
                            player.queue.extend(queue_list)
                            # 初始化音量（在播放第一首歌曲前）
                            await player.initialize_volume()
                        if player.is_paused:
                            await player.set_pause(False)
                        await player.play_next()
                        first_song_added = True
                else:
                    failed_songs.append(query)
            except Exception as e:
                logging.error(f"[process_playlist] 處理歌曲時發生錯誤：{str(e)}")
                failed_songs.append(query)
            if (index + 1) % 20 == 0 or index == len(search_queries) - 1:
                progress_embed.description = f"正在處理 {playlist_name}\n已完成 {index + 1}/{len(search_queries)} 首歌曲"
                await progress_message.edit(embed=progress_embed)
            await asyncio.sleep(0.1)
        
        # 為所有添加的歌曲設定請求者
        for track in added_songs:
            track.requester = interaction.user
        
        # 移除隊列中的第一首歌曲（因為已經在播放）
        if added_songs and player.queue:
            first_track = added_songs[0]
            queue_list = player.queue.get_queue()
            if first_track in queue_list:
                queue_list.remove(first_track)
                player.queue.clear()
                for track in queue_list:
                    player.queue.put(track)
        
        if not added_songs:
            embed = discord.Embed(
                title="⚠️ 播放失敗",
                description="播放清單可能無法播放任何歌曲",
                color=EMBED_COLORS['error']
            )
            await interaction.followup.send(embed=embed)
            return
        await send_playlist_results(interaction, added_songs, failed_songs, playlist_name)
    except Exception as e:
        logging.error(f"[process_playlist] 播放清單處理錯誤：{str(e)}")
        error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}")
        await interaction.followup.send(embed=error_embed)

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
        logging.error(f"Spotify 播放清單處理錯誤: {e}")
        return []