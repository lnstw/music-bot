import discord
from discord import app_commands
from discord.ext import commands
from core.embed import create_error_embed, check_voice_state_and_respond, EMBED_COLORS
from core.playlist import process_playlist, process_spotify_track, process_spotify_album, get_platform, process_spotify_playlist, process_youtube_playlist
from core.view import QueuePaginator
from core.player import CustomPlayer
from core.config import spotify
import logging

class Queue(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    qe = app_commands.Group(name="播放清單", description="播放清單相關指令")
    @qe.command(name="顯示", description="顯示目前的播放清單")
    async def queue(self, interaction: discord.Interaction):
        try:
            if not interaction.guild.voice_client:
                await interaction.followup.send("❌ 機器人不在語音頻道中！")
                return
            player: CustomPlayer = interaction.guild.voice_client
            await interaction.response.defer()
            queue_list = player.queue.get_queue()
            current_song = player.current
            status_parts = []
            is_loop = player.queue.is_looping
            if is_loop:
                status_parts.append("🔄 循環模式：開啟")
            paginator = QueuePaginator(interaction, queue_list, songs_per_page=10, current_song=current_song, status_parts=status_parts)
            embed = paginator.get_embed()
            await interaction.followup.send(embed=embed, view=paginator)
        except Exception as e:
            logging.error(f"顯示播放清單時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"顯示播放清單時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=error_embed)
    #==清空播放清單==
    @qe.command(name="清空", description="清空目前的播放清單")
    async def clear(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 機器人不在語音頻道中！")
            return
        player: CustomPlayer = interaction.guild.voice_client
        if player.queue.is_empty:
            await interaction.followup.send("❌ 播放清單（待播歌曲）已經是空的！")
            return
        player.queue.clear()
        is_looping = player.queue.loop_mode == lava_lyra.LoopMode.QUEUE
        embed = discord.Embed(
            title="🗑️ 已清空播放清單",
            description="已成功移除所有後續的待播歌曲，當前播放的歌曲不會受到影響。",
            color=EMBED_COLORS['success']
        )
        
        if is_looping:
            embed.set_footer(text="🔄 提醒：目前的「佇列循環模式」正開啟中")
        else:
            embed.set_footer(text="➡️ 提醒：目前的循環模式為「關閉」狀態")

        await interaction.followup.send(embed=embed)
    #==指定清除歌曲==
    @qe.command(name="移除", description="從播放清單中移除指定的歌曲")
    async def remove(self, interaction: discord.Interaction, position: int):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 機器人不在語音頻道中！")
            return
            
        player: CustomPlayer = interaction.guild.voice_client
        raw_queue = player.queue.get_queue() if hasattr(player.queue, 'get_queue') else list(player.queue)
        actual_queue_list = list(raw_queue)
        current_in_queue = False
        display_queue = list(actual_queue_list)
        if player.current and display_queue and display_queue[0].uri == player.current.uri:
            display_queue.pop(0)
            current_in_queue = True
        if not display_queue:
            await interaction.followup.send("❌ 播放清單是空的！")
            return
        if position < 1 or position > len(display_queue):
            await interaction.followup.send(f"❌ 無效的歌曲位置！目前待播中只有 1 ~ {len(display_queue)} 首歌曲。")
            return
        removed_song = display_queue[position - 1]
        actual_index = position if current_in_queue else (position - 1)
        actual_queue_list.pop(actual_index)
        player.queue.clear()
        for track in actual_queue_list:
            if hasattr(player.queue, 'put'):
                player.queue.put(track)
            else:
                player.queue.append(track)
        embed = discord.Embed(
            title="🗑️ 已移除歌曲",
            description=f"已從播放清單中移除第 `{position}` 首：\n[{removed_song.title}]({removed_song.uri})",
            color=EMBED_COLORS['success']
        )
        is_looping = player.queue.loop_mode == lava_lyra.LoopMode.QUEUE
        if is_looping:
            embed.set_footer(text="🔄 循環模式開啟中")
            
        await interaction.followup.send(embed=embed)
    #==隨機排序==
    @qe.command(name="隨機", description="將播放清單中的歌曲隨機排序")
    async def shuffle(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 機器人不在語音頻道中！")
            return
        guild_id = interaction.guild_id
        player: CustomPlayer = interaction.guild.voice_client
        if player.queue.is_empty:
            await interaction.followup.send("❌ 播放清單是空的！")
            return
        if player.queue.is_looping:
            current_song = player.current
            queue_list = player.queue.get_queue()
            if current_song in queue_list:
                player.queue.remove(current_song)
            player.queue.shuffle()
            if current_song:
                player.queue.put(current_song)
        else:
            player.queue.shuffle()
        embed = discord.Embed(
            title="🔀 已隨機排序播放清單",
            description=f"已重新排序 {len(player.queue.get_queue())} 首歌曲",
            color=EMBED_COLORS['success']
        )
        if player.queue.is_looping:
            embed.set_footer(text="🔄 循環模式開啟中")
        await interaction.followup.send(embed=embed)
    #==插入音樂==
    @qe.command(name="插入", description="插入音樂到下一首")
    async def insert(self, interaction: discord.Interaction, query: str):
        try:
            await interaction.response.defer()
            if not await check_voice_state_and_respond(interaction):
                return
            if not interaction.guild.voice_client:
                await interaction.followup.send("❌ 機器人不在語音頻道中！")
                return
            guild_id = interaction.guild_id
            player: CustomPlayer = interaction.guild.voice_client
            if player.queue.is_empty:
                commands = await self.bot.tree.fetch_commands()
                cmd_dict = {cmd.name: cmd.id for cmd in commands}
                cmd_id = cmd_dict.get("play", "00")
                error_embed = discord.Embed(title="",description=f"請先使用</play:{cmd_id}>",color=EMBED_COLORS["error"])
                await interaction.followup.send(embed=error_embed)
                return
            player._last_channel = interaction.channel
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
                    await process_playlist(
                        interaction=interaction,
                        search_queries=search_queries,
                        playlist_name="插播播放清單",
                        insert_next=True
                    )
                    return
                except Exception as e:
                    logging.error(f"處理播放清單時發生錯誤: {e}")
                    error_embed = create_error_embed(f"處理播放清單時發生錯誤：{str(e)}")
                    await interaction.followup.send(embed=error_embed)
                    return
            search_queries = []
            try:
                if platform == 'spotify':
                    if 'track' in query.lower():
                        search_query = await process_spotify_track(spotify, query)
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
                tracks = await player.get_tracks(search_queries[0])
                if tracks:
                    track = tracks[0]
                    track.requester = interaction.user
                    player.queue.put_at_index(0, track)
                    
                    embed = discord.Embed(
                        title="⏭️ 已加入下一首播放",
                        description=f"[{track.title}]({track.uri})",
                        color=EMBED_COLORS['success']
                    )
                    if track.thumbnail:
                        embed.set_thumbnail(url=track.thumbnail)
                    duration_sec = int(track.length / 1000) if track.length else 0
                    minutes = duration_sec // 60
                    seconds = duration_sec % 60
                    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
                    track_requester = track.requester.mention if track.requester else "未知用戶"
                    embed.add_field(name="請求者", value=track_requester, inline=True)
                    embed.add_field(name="平台", value=platform.title(), inline=True)
                    await interaction.followup.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="❌ 無法找到歌曲",
                        description="請嘗試其他連結或直接搜尋歌名",
                        color=EMBED_COLORS['error']
                    )
                    await interaction.followup.send(embed=embed)
            except Exception as e:
                logging.error(f"插播時發生錯誤：{str(e)}")
                error_embed = create_error_embed(f"插播時發生錯誤：{str(e)}")
                await interaction.followup.send(embed=error_embed)
        except Exception as e:
            logging.error(f"插播時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"插播時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=error_embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Queue(bot))