import discord
from discord import app_commands
from discord.ext import commands
from collections import deque
import random
import wavelink

from service.play import play_next, update_activity_time, Song
from service.Lavalink import LavalinkPlayerCompat
from service.playlist import process_playlist, process_spotify_track, process_spotify_album, get_platform, process_spotify_playlist, process_youtube_playlist
from service.embed import create_error_embed, check_voice_state_and_respond, EMBED_COLORS
from service.view import QueuePaginator


class Queue(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def get_client(self):
        return self.bot
    
    qe = app_commands.Group(name="播放清單", description="播放清單相關指令")
    #==顯示播放清單==
    @qe.command(name="顯示", description="顯示目前的播放清單")
    async def queue(self, interaction: discord.Interaction):
        try:
            client = self.get_client()
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
    #==清空播放清單==
    @qe.command(name="清空", description="清空目前的播放清單")
    async def clear(self, interaction: discord.Interaction):
        client = self.get_client()
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
    #==指定清除歌曲==
    @qe.command(name="移除", description="從播放清單中移除指定的歌曲")
    async def remove(self, interaction: discord.Interaction, position: int):
        client = self.get_client()
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
    #==隨機排序==
    @qe.command(name="隨機", description="將播放清單中的歌曲隨機排序")
    async def shuffle(self, interaction: discord.Interaction):
        client = self.get_client()
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
    #==插入音樂==
    @qe.command(name="插入", description="插入音樂到下一首")
    async def insert(self, interaction: discord.Interaction, query: str):
        client = self.get_client()
        await update_activity_time(interaction.guild_id, client)
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
                    vc: wavelink.Player = await interaction.user.voice.channel.connect(cls=LavalinkPlayerCompat)
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
                        await play_next(guild=interaction.guild, vc=vc, client=client)
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

async def setup(bot: commands.Bot):
    await bot.add_cog(Queue(bot))
