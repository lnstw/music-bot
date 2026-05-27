import discord, random
from typing import Optional
import wavelink
from collections import deque
from service.embed import create_now_playing_embed, create_error_embed, EMBED_COLORS
from service.channel import send_message_to_last_channel
import datetime
from datetime import timedelta

class Song:
    def __init__(self, url: str, title: str, duration: int, thumbnail: str, requester: discord.Member, platform: str):
        self.url = url
        self.title = title
        self.duration = duration
        self.thumbnail = thumbnail
        self.requester = requester
        self.platform = platform.lower()

async def update_activity_time(guild_id: int, client):
    client.last_activity[guild_id] = datetime.datetime.now()

async def play_next(guild: discord.Guild, vc: wavelink.Player, client):
    guild_id = guild.id
    if client.force_stop.get(guild_id, False):
        await client.update_presence()
        embed = discord.Embed(
                title="✅ 播放完成",
                description="播放清單已播放完畢",
                color=EMBED_COLORS['success']
        )
        await send_message_to_last_channel(guild_id=guild_id, embed=embed)
        return
    try:
        if not client.queues[guild_id]:
            if client.loop_mode.get(guild_id, False) and guild_id in client.current_songs:
                current_song = client.current_songs[guild_id]
                client.queues[guild_id].append(current_song)
            elif (guild_id in client.auto_recommend and 
                  client.auto_recommend[guild_id] and 
                  guild_id in client.current_songs):
                recommended_song = await get_next_recommendation(guild_id, client)
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
                    await client.update_presence(next_song.title)
                    if client.show_now_song.get(guild_id, False):
                        embed = create_now_playing_embed(next_song)
                        if client.loop_mode.get(guild_id, False):
                            queue_list = list(client.queues[guild_id])
                            total = len(queue_list)
                            embed.set_footer(text=f"🔄 循環播放中 總共 {total} 首")
                        await send_message_to_last_channel(guild_id=guild_id, embed=embed)
            except Exception as e:
                print(f"播放歌曲時發生錯誤: {e}")
                await play_next(guild=guild, vc=vc, client=client)
        else:
            await client.update_presence()
            embed = discord.Embed(
                title="✅ 播放完成",
                description="播放清單已播放完畢",
                color=EMBED_COLORS['success']
            )
            await send_message_to_last_channel(guild_id=guild_id, embed=embed)
    except Exception as e:
        print(f"播放下一首時發生錯誤：{e}")
        error_embed = create_error_embed(f"播放時發生錯誤：{str(e)}")
        await send_message_to_last_channel(guild_id=guild_id, embed=error_embed)

async def get_next_recommendation(guild_id: int, client) -> Optional[Song]:
    try:
        if guild_id in client.current_songs:
            current_song = client.current_songs[guild_id]
            return await get_recommendations(current_song)
    except Exception as e:
        print(f"獲取下一個推薦時發生錯誤：{e}")
    return None

async def get_recommendations(current_song: Song) -> Optional[Song]:
    try:
        search_query = f"{current_song.title} {current_song.artist}" if hasattr(current_song, "artist") else current_song.title
        tracks = await wavelink.Playable.search(search_query)
        tracks = [t for t in tracks if t.uri != current_song.url]
        if tracks:
            track = random.choice(tracks)
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