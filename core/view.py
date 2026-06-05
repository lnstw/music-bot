import discord
from discord.ui import Button , View
from discord.ext import commands
from discord import ui
import lava_lyra
import asyncio
from collections import deque
import datetime
import aiohttp
from io import BytesIO
import requests
from PIL import Image
import colorsys
from core.embed import create_error_embed, check_voice_state_and_respond, EMBED_COLORS
from core.player import CustomPlayer
import logging
from core.log import setup_logging
setup_logging()

class PlayPauseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⏯️", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.play_pause(interaction)

class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⏭️", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.next_play(interaction)

class LoopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔁", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.toggle_loop(interaction)

class QueueButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📃", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.show_queue(interaction)

class ShuffleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔀", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.shuffle_queue(interaction)

class RewindButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⏪", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.Rewind(interaction)

class ForwardButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⏩", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.forward(interaction)

class SoundMinusButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔉➖", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.decrease_volume(interaction)

class SoundPlusButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔉➕", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.increase_volume(interaction)

class UpdateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="更新", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        await self.view.update_status(interaction)

class MusicControlView(discord.ui.LayoutView):
    def __init__(self, track: lava_lyra.Track, player: CustomPlayer):
        super().__init__(timeout=None)

        try:
            duration = int(track.length / 1000) if track.length else 1
            position = max(0, int(player.position / 1000))
            position = min(position, duration)
            
            bar_length = 20
            filled = int((position / duration) * bar_length) if duration > 0 else 0
            progress_bar = "▬" * filled + "🔘" + "▬" * (bar_length - filled)
            current_time = f"{position // 60}:{position % 60:02d}"
            total_time = f"{duration // 60}:{duration % 60:02d}"
        except Exception as e:
            progress_bar = "▬" * 20
            current_time = "0:00"
            total_time = "0:00"

        if player.is_paused:
            status_title = f"# ⏸️ 已暫停\n[{track.title}]({track.uri})"
            accent_color = discord.Color.yellow()
        else:   
            status_title = f"# ▶️ 正在播放\n[{track.title}]({track.uri})"
            accent_color = discord.Color.green()

        loop_status = "🔄 開啟" if player.queue.is_looping else "➡️ 關閉"
        volume = getattr(player, 'volume', 100)
        requester_str = track.requester.mention if track.requester else "未知用戶"

        text = f"{status_title}\n\n**進度**\n{progress_bar}\n{current_time} / {total_time}\n\n**請求者**: {requester_str} | **循環播放**: {loop_status} | **音量**: 🔊 {volume}%"
        
        self.text_display = discord.ui.TextDisplay(text)

        if track.thumbnail:
            self.thumbnail = discord.ui.Thumbnail(media=track.thumbnail)
            self.section = discord.ui.Section(self.text_display, accessory=self.thumbnail)
        else:
            self.section = discord.ui.Section(self.text_display)

        self.action_row1 = discord.ui.ActionRow(PlayPauseButton(), NextButton(), LoopButton(), QueueButton(), ShuffleButton())
        self.action_row2 = discord.ui.ActionRow(RewindButton(), ForwardButton(), SoundMinusButton(), SoundPlusButton(), UpdateButton())
        
        container = discord.ui.Container(self.section, self.action_row1, self.action_row2, accent_color=accent_color)
        self.add_item(container)

    async def next_play(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 沒有歌曲正在播放！",silent=True)
            return    
        player: CustomPlayer = interaction.guild.voice_client
        if not player.is_playing and not player.current:
            await interaction.followup.send("❌ 沒有歌曲正在播放！",silent=True)
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
        await interaction.followup.send(embed=embed,silent=True)
        if hasattr(player, 'skip'):
            await player.skip()
        else:
            await player.stop()

    async def play_pause(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        player: CustomPlayer = interaction.guild.voice_client
        if player.is_paused:
            await player.set_pause(False)
            embed = discord.Embed(
                title="▶️ 已恢復播放",
                color=EMBED_COLORS['success']
            )
        elif player.is_playing:
            await player.set_pause(True)
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
        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)
    
    async def toggle_loop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        player: CustomPlayer = interaction.guild.voice_client
        if player.queue.loop_mode == lava_lyra.LoopMode.QUEUE:
            player.queue.set_loop_mode(lava_lyra.LoopMode.NONE)
            status = "關閉"
        else:
            player.queue.set_loop_mode(lava_lyra.LoopMode.QUEUE)
            status = "開啟"
        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(embed=None, view=view)
        embed = discord.Embed(
            title="🔁 循環模式設置",
            description=f"播放清單循環模式已{status}",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed, silent=True)

    async def show_queue(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            player: CustomPlayer = interaction.guild.voice_client
            queue_list = player.queue.get_queue()
            current_song = player.current
            status_parts = []
            is_queue_looping = player.queue.loop_mode == lava_lyra.LoopMode.QUEUE
            if is_queue_looping:
                status_parts.append("🔄 循環模式：開啟")
            paginator = QueuePaginator(interaction, queue_list, songs_per_page=10, current_song=current_song, status_parts=status_parts)
            embed = paginator.get_embed()
            await interaction.followup.send(f"{interaction.user.mention}", embed=embed, view=paginator,silent=True)
        except Exception as e:
            logging.error(f"顯示播放清單時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"顯示播放清單時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=error_embed,silent=True)
        
    async def shuffle_queue(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        player: CustomPlayer = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.followup.send("❌ 播放清單是空的！",silent=True)
            return
        if player.queue.is_looping:
            current_song = player.current
            player.queue.remove(current_song)
            player.queue.shuffle()
            player.queue.put_at_index(0, current_song)
        else:
            player.queue.shuffle()
        
        embed = discord.Embed(
            title="🔀 已打亂播放清單",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed,silent=True)
    
    async def Rewind(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        player: CustomPlayer = interaction.guild.voice_client
        if not player.is_playing:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        new_position = max(int(player.position) - 10000, 0)
        await player.seek(new_position)
        embed = discord.Embed(
            title="⏪ 已倒轉 10 秒",
            color=EMBED_COLORS['success']
        )
        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)
    
    async def forward(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        player: CustomPlayer = interaction.guild.voice_client
        if not player.is_playing:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        song = player.current
        new_position = min(int(player.position) + 10000, song.length * 1000)
        await player.seek(new_position)
        embed = discord.Embed(
            title="⏩ 已快轉 10 秒",
            color=EMBED_COLORS['success']
        )
        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)

    async def increase_volume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        player: CustomPlayer = interaction.guild.voice_client
        current_volume = player.volume
        new_volume = min(current_volume + 5, 200)
        await player.set_volume(new_volume)
        embed = discord.Embed(
            title="🔊 音量增加",
            description=f"音量已設置為 {new_volume}%",
            color=EMBED_COLORS['success']
        )
        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)
    
    async def decrease_volume(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        player: CustomPlayer = interaction.guild.voice_client
        current_volume = player.volume
        new_volume = max(current_volume - 5, 0)
        await player.set_volume(new_volume)
        embed = discord.Embed(
            title="🔊 音量減少",
            description=f"音量已設置為 {new_volume}%",
            color=EMBED_COLORS['success']
        )
        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)

    async def update_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有連線到語音頻道！", embed=None, view=None)
            return
        
        guild_id = interaction.guild_id
        player: CustomPlayer = interaction.guild.voice_client
        if not player or not player.is_playing:
            view = playend()
            await interaction.edit_original_response(view=view)
            return

        song = player.current
        view = MusicControlView(song, player)
        await interaction.edit_original_response(view=view)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        try:
            view = timeout()
            if not interaction.response.is_done():
                await interaction.response.edit_message(view=view)
            else:
                await interaction.edit_original_response(view=view)
        except Exception:
            if interaction.message:
                await interaction.message.edit(view=view)

    async def on_timeout(self) -> None:
        if hasattr(self, "message") and self.message and isinstance(self.message, discord.Message):
            try:
                await self.message.edit(view=playend())
            except Exception:
                pass

class playend(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        text_content = "# ⚠️ 未在播放或播放完成"
        self.text_display = ui.TextDisplay(text_content)
        container = ui.Container(
            self.text_display, 
            accent_color=discord.Color.yellow()
        )
        self.add_item(container)

class timeout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        text_content = "# ⚠️ 按鈕已失效\n\n### 此互動已失敗或已過期，請重新使用 /musiccontrol 取得新的控制面板。"
        self.text_display = ui.TextDisplay(text_content)
        container = ui.Container(
            self.text_display, 
            accent_color=discord.Color.yellow()
        )
        self.add_item(container)

from discord.ui import View, Button

class QueuePaginator(View):
    def __init__(self, interaction, queue_list, songs_per_page=10, current_song=None, status_parts=None):
        super().__init__(timeout=60)
        self.interaction: discord.Interaction = interaction
        self.queue_list: list[lava_lyra.Track] = queue_list
        self.current_song: lava_lyra.Track | None = current_song
        self.status_parts = status_parts or []
        
        self.page = 0
        self.songs_per_page = songs_per_page
        
        # 預先計算好每一頁「真正能容納的歌曲範圍」，徹底解決因字數截斷導致的跳行 Bug
        self.page_ranges = self._calculate_pages()
        self.total_pages = len(self.page_ranges) or 1

        self.prev_button = Button(label="上一頁", style=discord.ButtonStyle.primary)
        self.next_button = Button(label="下一頁", style=discord.ButtonStyle.primary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.update_buttons()

    def _calculate_pages(self) -> list[tuple[int, int]]:
        """動態計算分頁範圍，確保每一頁的 Embed Field 絕對不會超過 1024 字元"""
        pages = []
        start_idx = 0
        total_songs = len(self.queue_list)
        
        while start_idx < total_songs:
            current_length = 0
            end_idx = start_idx
            while end_idx < total_songs and (end_idx - start_idx) < self.songs_per_page:
                song = self.queue_list[end_idx]
                duration_sec = int(song.length / 1000) if song.length else 0
                duration = f"{duration_sec//60}:{duration_sec%60:02d}"
                title = song.title[:50] + "..." if len(song.title) > 50 else song.title
                line = f"`{end_idx+1}.` [{title}]({song.uri}) | `{duration}`\n"
                if current_length + len(line) > 950:
                    break                  
                current_length += len(line)
                end_idx += 1
            if end_idx == start_idx:
                end_idx += 1
                
            pages.append((start_idx, end_idx))
            start_idx = end_idx
            
        return pages

    def update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    def get_embed(self):
        embed = discord.Embed(
            title=f"📃 播放清單 (第 {self.page+1}/{self.total_pages} 頁)",
            color=EMBED_COLORS['info']
        )
        if self.status_parts:
            embed.description = " | ".join(self.status_parts)
            
        if self.current_song:
            duration_sec = int(self.current_song.length / 1000) if self.current_song.length else 0
            duration = f"{duration_sec//60}:{duration_sec%60:02d}"
            current_song_requester = self.current_song.requester.mention if self.current_song.requester else "未知用戶"
            current_text = f"[{self.current_song.title}]({self.current_song.uri})\n`{duration}` | {current_song_requester}"
            embed.add_field(name="🎵 正在播放", value=current_text, inline=False)
            
        description = ""
        display_start = 0
        display_end = 0
        
        if self.page_ranges and self.page < len(self.page_ranges):
            start_idx, end_idx = self.page_ranges[self.page]
            display_start = start_idx + 1
            display_end = end_idx
            
            for idx in range(start_idx, end_idx):
                song = self.queue_list[idx]
                duration_sec = int(song.length / 1000) if song.length else 0
                duration = f"{duration_sec//60}:{duration_sec%60:02d}"
                
                title = song.title[:50] + "..." if len(song.title) > 50 else song.title
                line = f"`{idx+1}.` [{title}]({song.uri}) | `{duration}`\n"
                description += line

            if (end_idx - start_idx) < self.songs_per_page and end_idx < len(self.queue_list):
                description += "-# 翻頁後還有更多歌曲..."
        
        if not description:
            description = "播放清單是空的"
            
        embed.add_field(
            name=f"📋 待播清單 ({display_start}-{display_end}/{len(self.queue_list)})",
            value=description,
            inline=False
        )
        total_duration_ms = sum(s.length for s in self.queue_list)
        total_duration = int(total_duration_ms / 1000)  
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        seconds = total_duration % 60
        
        if len(self.queue_list) > 0:
            if hours > 0:
                embed.set_footer(text=f"總時長: {hours}:{minutes:02d}:{seconds:02d}")
            else:
                embed.set_footer(text=f"總時長: {minutes:02d}:{seconds:02d}")
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

class opselect_view(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.add_item(OpSelect(bot=bot))

class LavalinkStatusView(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed]):
        super().__init__(timeout=60)
        self.embeds = embeds
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.previous.disabled = self.current_page == 0
        self.next.disabled = self.current_page >= len(self.embeds) - 1

    @discord.ui.button(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.format_embed(), view=self)

    @discord.ui.button(label="➡️ 下一頁", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.format_embed(), view=self)

    def format_embed(self):
        embed = self.embeds[self.current_page]
        embed.set_footer(text=f"第 {self.current_page + 1} / {len(self.embeds)} 頁｜總計 {len(self.embeds)} 個伺服器正在播放")
        return embed

class OpSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, custom_options: list = None, placeholder: str = "選擇功能"):
        
        super().__init__(
            placeholder=placeholder, 
            min_values=1, 
            max_values=1, 
            options=custom_options, 
            custom_id="persistent_view:op_select"
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        op_select = self.values[0]
        if op_select == "Lavalink 播放狀態":
            embeds = []
            for guild in self.bot.guilds:
                if guild.voice_client and isinstance(guild.voice_client, CustomPlayer) and guild.voice_client.is_playing:
                    player: CustomPlayer = interaction.guild.voice_client
                    current_song = player.current
                    queue_length = player.queue.count
                    status_parts = []
                    if player.queue.is_looping:
                        status_parts.append("🔄循環")
                    voice_channel = guild.voice_client.channel
                    member_count = len([m for m in voice_channel.members if not m.bot])

                    embed = discord.Embed(
                        title="🎵 Lavalink 播放狀態",
                        description=f"📡 {guild.name}",
                        color=EMBED_COLORS['info']
                    )
                    embed.add_field(name="🎵 播放中", value=current_song.title if current_song else "未知", inline=False)
                    embed.add_field(name="👥 頻道", value=f"{voice_channel.name} ({member_count}人在線)", inline=True)
                    embed.add_field(name="📋 佇列", value=f"{queue_length} 首", inline=True)
                    embed.add_field(name="⚙️ 狀態", value=' | '.join(status_parts) if status_parts else '➡️ 一般播放', inline=False)
                    embeds.append(embed)

            if not embeds:
                embed = discord.Embed(
                    title="🎵 Lavalink 播放狀態",
                    description="目前沒有伺服器正在播放音樂",
                    color=EMBED_COLORS['info']
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                view = LavalinkStatusView(embeds)
                await interaction.response.send_message(embed=view.format_embed(), view=view, ephemeral=True)
        if op_select == "更新機器人狀態":
            for guild in self.bot.guilds:
                if guild.voice_client and isinstance(guild.voice_client, CustomPlayer) and guild.voice_client.is_playing:
                    player: CustomPlayer = interaction.guild.voice_client
                    current_song = player.current
                    if current_song:
                        await interaction.response.send_message("✅ 已更新音樂機器人狀態顯示", ephemeral=True)
                        return
            await interaction.response.send_message("✅ 已更新音樂機器人狀態顯示", ephemeral=True)

class RefreshButton(discord.ui.View):
    def __init__(self, image_url: str = None):
        super().__init__(timeout=None)
        if image_url:
            self.add_item(discord.ui.Button(label="點我跳轉", url=image_url, style=discord.ButtonStyle.link))

    @discord.ui.button(label="重新取得", style=discord.ButtonStyle.primary, custom_id="refresh_button")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        ref_embed = discord.Embed(title="<a:loading:1429472831103832195> 重新取得中...", color=discord.Color.yellow())
        await interaction.response.edit_message(embed=ref_embed, view=None)

        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.redbean0721.com/api/img?type=json") as api_response:
                end_time = datetime.datetime.now()
                if api_response.status != 200:
                    await interaction.edit_original_response(content="無法獲取圖片，請稍後再試。")
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
                await interaction.edit_original_response(embed=embed, view=view, attachments=[file])

async def get_dominant_color(url):
    def sync_get_color():
        try:
            response = requests.get(url, timeout=10)
            img = Image.open(BytesIO(response.content))
            img = img.resize((50, 50)).convert('RGB')
            pixels = list(img.getdata())
            r_avg = sum(p[0] for p in pixels) // len(pixels)
            g_avg = sum(p[1] for p in pixels) // len(pixels)
            b_avg = sum(p[2] for p in pixels) // len(pixels)
            h, s, v = colorsys.rgb_to_hsv(r_avg/255, g_avg/255, b_avg/255)
            v = max(min(v * 1.5, 1.0), 0.5)
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return discord.Color.from_rgb(int(r*255), int(g*255), int(b*255))
        except:
            return discord.Color.green()

    return await asyncio.to_thread(sync_get_color)


HELP_CATEGORIES = {
    "music": {
        "title": "🎵 音樂控制",
        "commands": [
            {
                "path": "音樂 播放",
                "description": "播放音樂",
                "usage": "使用方法: `/音樂 播放 [連結或關鍵字]`",
            },
            {
                "path": "音樂 暫停",
                "description": "暫停音樂",
                "usage": "使用方法: `/音樂 暫停`",
            },
            {
                "path": "音樂 繼續",
                "description": "繼續播放",
                "usage": "使用方法: `/音樂 繼續`",
            },
            {
                "path": "音樂 跳過",
                "description": "跳過目前的歌曲",
                "usage": "使用方法: `/音樂 跳過`",
            },
            {
                "path": "音樂 音量",
                "description": "調整音樂音量",
                "usage": "使用方法: `/音樂 音量 [數字]`",
            },
            {
                "path": "音樂 控制器",
                "description": "叫出音樂控制器",
                "usage": "使用方法: `/音樂 控制器`",
            },
            {
                "path": "音樂 循環",
                "description": "切換循環播放模式",
                "usage": "使用方法: `/循環`",
            }
        ],
    },
    "queue": {
        "title": "🧾 播放清單控制",
        "commands": [
            {
                "path": "播放清單 顯示",
                "description": "顯示目前的播放清單",
                "usage": "使用方法: `/播放清單 顯示`",
            },
            {
                "path": "播放清單 清空",
                "description": "清空目前的播放清單",
                "usage": "使用方法: `/播放清單 清空`",
            },
            {
                "path": "播放清單 移除",
                "description": "從播放清單中移除指定的歌曲",
                "usage": "使用方法: `/播放清單 移除 [位置]`",
            },
            {
                "path": "播放清單 隨機",
                "description": "將播放清單中的歌曲隨機排序",
                "usage": "使用方法: `/播放清單 隨機`",
            },
            {
                "path": "播放清單 插入",
                "description": "插入音樂到下一首",
                "usage": "使用方法: `/播放清單 插入 [連結或關鍵字]`",
            }
        ],
    },
    "bot": {
        "title": "🤖 機器人控制",
        "commands": [
            {
                "path": "機器人 離開",
                "description": "將機器人從語音頻道中踢出",
                "usage": "使用方法: `/機器人 離開`",
            },
            {
                "path": "機器人 重載",
                "description": "重載機器人",
                "usage": "使用方法: `/機器人 重載`",
            }
        ]
    },
    "other": {
        "title": "🤖 其他功能",
        "commands": [
            {
                "path": "ping",
                "description": "檢查機器人延遲",
                "usage": "使用方法: `/ping`",
            },
            {
                "path": "邀請機器人",
                "description": "獲取機器人邀請連結",
                "usage": "使用方法: `/邀請機器人`",
            },
            {
                "path": "現正播放訊息",
                "description": "開啟/關閉目前歌曲的提示訊息",
                "usage": "使用方法: `/現正播放訊息`",
            },
            {
                "path": "隨機圖",
                "description": "可以隨機給你一張圖片",
                "usage": "使用方法: `/隨機圖 [標籤(可選)]`",
            },
            {
                "path": "停止",
                "description": "停止機器人並清空播放清單",
                "usage": "使用方法: `/停止`",
            }

        ],
    }
}

def build_command_id_lookup(commands) -> dict:
    lookup = {}

    def walk(command, parents=()):
        command_name = " ".join((*parents, command.name)).strip()
        command_id = getattr(command, "id", None)
        if command_id is not None:
            lookup[command_name] = command_id

        for option in getattr(command, "options", []) or []:
            option_type = str(getattr(option, "type", "")).lower()
            if "subcommand" not in option_type:
                continue

            option_name = getattr(option, "name", None)
            if not option_name:
                continue

            option_path = " ".join((*parents, command.name, option_name)).strip()
            lookup[option_path] = getattr(option, "id", None) or command_id
            if getattr(option, "options", None):
                walk(option, (*parents, command.name))

    for command in commands:
        walk(command)

    return lookup


class CategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🎵 音樂播放", description="查看基本播放命令", value="music"),
            discord.SelectOption(label="🧾 播放清單控制", description="管理播放清單", value="queue"),
            discord.SelectOption(label="🤖 機器人控制", description="踢出,重載機器人", value="bot"),
            discord.SelectOption(label="🤖 其他", description="其他功能", value="other")
        ]
        super().__init__(placeholder="選擇一個分類...", options=options, custom_id="category_select")

    async def callback(self, interaction: discord.Interaction):
        try:
            commands = await interaction.client.tree.fetch_commands()
        except Exception:
            commands = []

        command_ids = build_command_id_lookup(commands)
        category = self.values[0]
        category_data = HELP_CATEGORIES.get(category)
        if not category_data:
            await interaction.response.send_message("找不到該分類。", ephemeral=True)
            return

        view = CommandSelectView(category_data["commands"], command_ids, category_data["title"])
        embed = discord.Embed(
            title=category_data["title"],
            description="請從下方選單選擇一個命令以查看詳細資訊",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class CategorySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CategorySelect())


class CommandSelect(discord.ui.Select):
    def __init__(self, commands_info: list[dict], command_ids: dict, category_title: str):
        if isinstance(commands_info, dict):
            normalized_commands = []
            for command_path, command_value in commands_info.items():
                if isinstance(command_value, dict):
                    normalized_commands.append(
                        {
                            "path": command_path,
                            "description": command_value.get("description", ""),
                            "usage": command_value.get("usage", command_value.get("description", "")),
                        }
                    )
                else:
                    normalized_commands.append(
                        {
                            "path": command_path,
                            "description": str(command_value),
                            "usage": str(command_value),
                        }
                    )
            commands_info = normalized_commands

        self.commands_info = commands_info
        self.command_ids = command_ids or {}
        self.category_title = category_title
        options = [
            discord.SelectOption(
                label=command_info["path"][:100],
                description=command_info["description"][:100],
                value=command_info["path"],
            )
            for command_info in commands_info
        ]
        super().__init__(placeholder="選擇一個命令...", options=options, custom_id="command_select")

    async def callback(self, interaction: discord.Interaction):
        cmd_path = self.values[0]
        command_info = next((item for item in self.commands_info if item["path"] == cmd_path), None)
        if not command_info:
            await interaction.response.send_message("找不到該命令。", ephemeral=True)
            return

        cmd_id = self.command_ids.get(cmd_path)
        desc = command_info["description"]
        usage = command_info["usage"]
        title = f"</{cmd_path}:{cmd_id}>" if cmd_id else f"/{cmd_path}"

        embed = discord.Embed(
            title=title,
            description=f"**說明:**\n{desc}\n\n**{usage}**",
            color=discord.Color.green(),
        )
        view = CommandDetailView()
        await interaction.response.edit_message(embed=embed, view=view)


class CommandSelectView(discord.ui.View):
    def __init__(self, commands_info, command_ids, category_title: str):
        super().__init__(timeout=None)
        commands_info = commands_info or []
        command_ids = command_ids or {}
        self.add_item(CommandSelect(commands_info, command_ids, category_title))
        back_button = discord.ui.Button(
            label="返回分類選擇",
            style=discord.ButtonStyle.gray,
            emoji="◀️",
            custom_id="cmd_back_to_category",
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        view = CategorySelectView()
        embed = discord.Embed(
            title="📚 命令幫助",
            description="請從下方選單選擇一個分類以查看相關命令",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class CommandDetailView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        back_button = discord.ui.Button(
            label="重新選擇",
            style=discord.ButtonStyle.primary,
            emoji="🔄",
            custom_id="cmd_detail_back",
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        view = CategorySelectView()
        embed = discord.Embed(
            title="📚 命令幫助",
            description="請從下方選單選擇一個分類以查看相關命令",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)