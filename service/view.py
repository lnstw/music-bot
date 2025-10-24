import discord
from discord.ui import Button , View
import random
import wavelink
import asyncio
from collections import deque
from core import MusicClient, EMBED_COLORS
from service.embed import create_music_embed, create_error_embed, check_voice_state_and_respond

client = MusicClient()

class MusicControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.play_button = Button(label="⏯️", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="⏭️", style=discord.ButtonStyle.primary)
        self.loop_button = Button(label="🔁", style=discord.ButtonStyle.primary)
        self.queue_button = Button(label="📃", style=discord.ButtonStyle.primary)
        self.shuffle_button = Button(label="🔀", style=discord.ButtonStyle.primary)
        self.Rewind_button = Button(label="⏪", style=discord.ButtonStyle.primary)
        self.forward_button = Button(label="⏩", style=discord.ButtonStyle.primary)
        self.sound_minus_button = Button(label="🔉➖", style=discord.ButtonStyle.primary)
        self.sound_plus_button = Button(label="🔉➕", style=discord.ButtonStyle.primary)
        self.update_button = Button(label="更新", style=discord.ButtonStyle.primary)

        self.next_button.callback = self.next_play
        self.play_button.callback = self.play_pause
        self.loop_button.callback = self.toggle_loop
        self.queue_button.callback = self.show_queue
        self.shuffle_button.callback = self.shuffle_queue
        self.Rewind_button.callback = self.Rewind
        self.forward_button.callback = self.forward
        self.sound_minus_button.callback = self.decrease_volume
        self.sound_plus_button.callback = self.increase_volume
        self.update_button.callback = self.update_status

        self.add_item(self.play_button)
        self.add_item(self.next_button)
        self.add_item(self.loop_button)
        self.add_item(self.queue_button)
        self.add_item(self.shuffle_button)
        self.add_item(self.Rewind_button)
        self.add_item(self.forward_button)
        self.add_item(self.sound_minus_button)
        self.add_item(self.sound_plus_button)
        self.add_item(self.update_button)

    async def next_play(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        guild_id = interaction.guild_id
        if not vc.playing:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
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
        await interaction.followup.send(embed=embed, ephemeral=True)
        await vc.stop()

    async def play_pause(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        if vc.paused:
            await vc.pause(False)
            embed = discord.Embed(
                title="▶️ 已恢復播放",
                color=EMBED_COLORS['success']
            )
        elif vc.playing:
            await vc.pause(True)
            embed = discord.Embed(
                title="⏸️ 已暫停播放",
                color=EMBED_COLORS['success']
            )
        else:
            embed = discord.Embed(
                title="❌ 沒有歌曲正在播放！",
                color=EMBED_COLORS['error']
            )
        guild_id = interaction.guild_id
        song = client.current_songs.get(guild_id)
        updated_embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=updated_embed, view=view)
        await interaction.followup.send(embed=embed)
    
    async def toggle_loop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        if guild_id not in client.loop_mode:
            client.loop_mode[guild_id] = False
        client.loop_mode[guild_id] = not client.loop_mode[guild_id]
        status = "開啟" if client.loop_mode[guild_id] else "關閉"
        vc: wavelink.Player = interaction.guild.voice_client
        song = client.current_songs.get(guild_id)
        updated_embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=updated_embed, view=view)
        embed = discord.Embed(
            title="🔁 循環模式設置",
            description=f"循環模式已{status}",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed)

    async def show_queue(self, interaction: discord.Interaction):
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
            await interaction.followup.send(f"{interaction.user.mention}", embed=embed, view=paginator)
        except Exception as e:
            print(f"顯示播放清單時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"顯示播放清單時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=error_embed)
        
    async def shuffle_queue(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        if guild_id not in client.queues or not client.queues[guild_id]:
            await interaction.followup.send("❌ 播放清單是空的！")
            return
        queue_list = list(client.queues[guild_id])
        if client.loop_mode.get(guild_id, False):
            current_song = client.current_songs.get(guild_id)
            queue_list.remove(current_song)
            random.shuffle(queue_list)
            queue_list.insert(0, current_song)
        else:
            random.shuffle(queue_list)
        client.queues[guild_id] = deque(queue_list)
        embed = discord.Embed(
            title="🔀 已打亂播放清單",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed)
    
    async def Rewind(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc.playing:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        new_position = max(int(vc.position) - 10000, 0)
        await vc.seek(new_position)
        embed = discord.Embed(
            title="⏪ 已倒轉 10 秒",
            color=EMBED_COLORS['success']
        )
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        song = client.current_songs.get(guild_id)
        updated_embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=updated_embed, view=view)
        await interaction.followup.send(embed=embed)
    
    async def forward(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc.playing:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        guild_id = interaction.guild_id
        song = client.current_songs.get(guild_id)
        new_position = min(int(vc.position) + 10000, song.duration * 1000)
        await vc.seek(new_position)
        embed = discord.Embed(
            title="⏩ 已快轉 10 秒",
            color=EMBED_COLORS['success']
        )
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        song = client.current_songs.get(guild_id)
        updated_embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=updated_embed, view=view)
        await interaction.followup.send(embed=embed)

    async def increase_volume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        current_volume = getattr(vc, 'volume', 100)
        new_volume = min(current_volume + 5, 200)
        await vc.set_volume(new_volume)
        embed = discord.Embed(
            title="🔊 音量增加",
            description=f"音量已設置為 {new_volume}%",
            color=EMBED_COLORS['success']
        )
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        song = client.current_songs.get(guild_id)
        updated_embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=updated_embed, view=view)
        await interaction.followup.send(embed=embed)
    
    async def decrease_volume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        current_volume = getattr(vc, 'volume', 100)
        new_volume = max(current_volume - 5, 0)
        await vc.set_volume(new_volume)
        embed = discord.Embed(
            title="🔊 音量減少",
            description=f"音量已設置為 {new_volume}%",
            color=EMBED_COLORS['success']
        )
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        song = client.current_songs.get(guild_id)
        updated_embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=updated_embed, view=view)
        await interaction.followup.send(embed=embed)

    async def update_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            embed = discord.Embed(
                    title="⚠️ 未在播放或播放完成",
                    color=EMBED_COLORS['warning']
                )
            await interaction.edit_original_response(embed=embed, view=None)
        song = client.current_songs.get(guild_id)
        embed = create_music_embed(client, song, vc, guild_id)
        view = MusicControlView()
        await interaction.edit_original_response(embed=embed, view=view)
        async def auto_update():
            while True:
                await asyncio.sleep(20)
                if not vc or not vc.playing:
                    embed = discord.Embed(
                        title="⚠️ 未在播放或播放完成",
                        color=EMBED_COLORS['warning']
                    )
                    await interaction.edit_original_response(embed=embed, view=None)
                    break
                updated_embed = create_music_embed(client, song, vc, guild_id)
                await interaction.edit_original_response(embed=updated_embed, view=view)
            asyncio.create_task(auto_update())

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