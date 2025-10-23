import asyncio
import discord
from typing import Optional
from urllib.parse import urlparse
import wavelink
from core import MusicClient, EMBED_COLORS, Song
from service.embed import create_error_embed
from service.play import play_next
from service.embed import create_music_embed
from service.view import MusicControlView

client = MusicClient()

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

async def send_playlist_results(client: MusicClient, interaction: discord.Interaction, added_songs: list, failed_songs: list, playlist_name: str):
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
        await interaction.edit_original_response(embed=embed)

        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        song = client.current_songs.get(guild_id)
        embed2 = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        message = await interaction.followup.send(embed=embed2, view=view)
        async def auto_update():
            while True:
                await asyncio.sleep(20)
                if not vc or not vc.playing:
                    embed = discord.Embed(
                        title="⚠️ 未在播放或播放完成",
                        color=EMBED_COLORS['warning']
                    )
                    await message.edit(embed=embed, view=None)
                    break
                updated_embed = create_music_embed(client, song, vc, guild_id)
                await message.edit(embed=updated_embed, view=view)

    asyncio.create_task(auto_update())
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
        elif failed_songs:
            failed_embed = discord.Embed(
                title="❌ 處理失敗歌曲清單",
                description="\n".join(f"{i+1}. {song}" for i, song in enumerate(failed_songs)),
                color=EMBED_COLORS['error']
            )
            await interaction.edit_original_response(embed=failed_embed)
    else:
        await interaction.edit_original_response(embed=embed)

async def process_playlist(client, interaction: discord.Interaction, search_queries: list[str], playlist_name: str):
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
        first_song_played = False
        for index, query in enumerate(search_queries):
            try:
                tracks = await wavelink.Playable.search(query)
                if tracks and tracks[0] is not None:
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
                    added_songs.append(song)
                    if not first_song_played and not interaction.guild.voice_client.playing:
                        await play_next(client=client, guild=interaction.guild, vc=interaction.guild.voice_client)
                        first_song_played = True
                else:
                    failed_songs.append(query)
            except Exception as e:
                print(f"處理歌曲時發生錯誤：{str(e)}")
                failed_songs.append(query)
            if (index + 1) % 20 == 0 or index == len(search_queries) - 1:
                progress_embed.description = f"正在處理 {playlist_name}\n已完成 {index + 1}/{len(search_queries)} 首歌曲"
                await progress_message.edit(embed=progress_embed)
            await asyncio.sleep(0.1)
        await send_playlist_results(client, interaction, added_songs, failed_songs, playlist_name)
    except Exception as e:
        print(f"處理播放清單時發生錯誤：{str(e)}")
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
        print(f"Spotify 播放清單處理錯誤: {e}")
        return []
    