import discord
from discord.ui import Button , View
import random
import wavelink
import asyncio
from collections import deque
import datetime
from datetime import timedelta
import aiohttp
from io import BytesIO
import requests
from PIL import Image
import colorsys
from service.embed import create_error_embed, check_voice_state_and_respond, start_auto_update, EMBED_COLORS

_client = None
def set_client_ref(client):
    global _client
    _client = client

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
    def __init__(self, song, vc, guild_id, client=None):
        super().__init__(timeout=None)
        if client is None:
            client = _client

        try:
            duration = song.duration
            position = int(vc.position) // 1000
            position = min(position, duration)
            bar_length = 20
            filled = int((position / duration) * bar_length) if duration > 0 else 0
            progress_bar = "▬" * filled + "🔘" + "▬" * (bar_length - filled)
            current_time = f"{position // 60}:{position % 60:02d}"
            total_time = f"{duration // 60}:{duration % 60:02d}"
        except Exception:
            progress_bar = "▬" * 20
            current_time = "0:00"
            total_time = "0:00"

        if vc.paused:
            status_title = f"# ⏸️ 已暫停\n[{song.title}]({song.url})"
            accent_color = discord.Color.yellow()
        else:   
            status_title = f"# ▶️ 正在播放\n[{song.title}]({song.url})"
            accent_color = discord.Color.green()

        loop_status = "🔄 開啟" if client and client.loop_mode.get(guild_id, False) else "➡️ 關閉"
        volume = getattr(vc, 'volume', 100)

        text = f"{status_title}\n\n**進度**\n{progress_bar}\n{current_time} / {total_time}\n\n**請求者**: {song.requester.mention} | **循環播放**: {loop_status} | **音量**: 🔊 {volume}%\n\n*好聽嗎? • 音樂控制器請使用最底下的或是使用(/musiccontrol) :D*"
        
        self.text_display = discord.ui.TextDisplay(text)

        if song.thumbnail:
            self.thumbnail = discord.ui.Thumbnail(media=song.thumbnail)
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
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        vc: wavelink.Player = interaction.guild.voice_client
        guild_id = interaction.guild_id
        if not vc.playing:
            await interaction.edit_original_response(content="❌ 沒有歌曲正在播放！", embed=None, view=None)
            return
        next_song = None
        if  _client.loop_mode.get(guild_id, False) and _client.queues[guild_id]:
            current_song = _client.current_songs[guild_id]
            queue_list = list(_client.queues[guild_id])
            current_index = queue_list.index(current_song)
            next_index = (current_index + 1) % len(queue_list)
            next_song = queue_list[next_index]
        elif _client.queues[guild_id]:
            next_song = _client.queues[guild_id][0]
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
        await interaction.followup.send(embed=embed,silent=True)
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
        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)
    
    async def toggle_loop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        if guild_id not in _client.loop_mode:
            _client.loop_mode[guild_id] = False
        _client.loop_mode[guild_id] = not _client.loop_mode[guild_id]
        status = "開啟" if _client.loop_mode[guild_id] else "關閉"
        vc: wavelink.Player = interaction.guild.voice_client
        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        embed = discord.Embed(
            title="🔁 循環模式設置",
            description=f"循環模式已{status}",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed,silent=True)

    async def show_queue(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            guild_id = interaction.guild_id
            if guild_id not in _client.queues:
                _client.queues[guild_id] = deque()
            queue_list = list(_client.queues[guild_id])
            current_song = _client.current_songs.get(guild_id)
            status_parts = []
            is_loop = _client.loop_mode.get(guild_id, False)
            if is_loop:
                status_parts.append("🔄 循環模式：開啟")
            if guild_id in _client.auto_recommend and _client.auto_recommend[guild_id]:
                status_parts.append("✨ 自動推薦：開啟")
            paginator = QueuePaginator(interaction, queue_list, songs_per_page=10, current_song=current_song, status_parts=status_parts)
            embed = paginator.get_embed()
            await interaction.followup.send(f"{interaction.user.mention}", embed=embed, view=paginator,silent=True)
        except Exception as e:
            print(f"顯示播放清單時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"顯示播放清單時發生錯誤：{str(e)}")
            await interaction.followup.send(embed=error_embed,silent=True)
        
    async def shuffle_queue(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
            return
        guild_id = interaction.guild_id
        if guild_id not in _client.queues or not _client.queues[guild_id]:
            await interaction.followup.send("❌ 播放清單是空的！",silent=True)
            return
        queue_list = list(_client.queues[guild_id])
        if _client.loop_mode.get(guild_id, False):
            current_song = _client.current_songs.get(guild_id)
            queue_list.remove(current_song)
            random.shuffle(queue_list)
            queue_list.insert(0, current_song)
        else:
            random.shuffle(queue_list)
        _client.queues[guild_id] = deque(queue_list)
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
        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)
    
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
        song = _client.current_songs.get(guild_id)
        new_position = min(int(vc.position) + 10000, song.duration * 1000)
        await vc.seek(new_position)
        embed = discord.Embed(
            title="⏩ 已快轉 10 秒",
            color=EMBED_COLORS['success']
        )
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)

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
        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)
    
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
        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        await interaction.followup.send(embed=embed,silent=True)

    async def update_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild.voice_client:
            await interaction.edit_original_response(content="❌ 沒有連線到語音頻道！", embed=None, view=None)
            return
        
        guild_id = interaction.guild_id
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.playing:
            embed = discord.Embed(
                    title="⚠️ 未在播放或播放完成",
                    color=EMBED_COLORS['warning']
                )
            await interaction.edit_original_response(embed=embed, view=None)
            return

        song = _client.current_songs.get(guild_id)
        view = MusicControlView(song, vc, guild_id, _client)
        await interaction.edit_original_response(embed=None, view=view)
        await start_auto_update(guild_id, vc, interaction.message, view) 

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        embed = discord.Embed(
            title="⚠️ 按鈕已失效",
            description="此互動已失敗或已過期，請重新使用 /musiccontrol 取得新的控制面板。",
            color=EMBED_COLORS["warning"]
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.edit_original_response(embed=embed, view=None)
        except Exception:
            if interaction.message:
                await interaction.message.edit(embed=embed, view=None)

    async def on_timeout(self) -> None:
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass

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

class opselect_view(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(opselect())

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

class opselect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Lavalink 播放狀態", value="Lavalink 播放狀態"),
            discord.SelectOption(label="更新機器人狀態", value="更新機器人狀態")
        ]
        super().__init__(placeholder="選擇功能", min_values=1, max_values=1, options=options, custom_id="persistent_view:op_select")
    async def callback(self, interaction: discord.Interaction):
        op_select = self.values[0]
        if op_select == "Lavalink 播放狀態":
            embeds = []
            for guild in _client.guilds:
                if guild.voice_client and guild.voice_client.playing:
                    current_song = _client.current_songs.get(guild.id)
                    queue_length = len(_client.queues[guild.id]) if guild.id in _client.queues else 0
                    status_parts = []
                    if _client.loop_mode.get(guild.id, False):
                        status_parts.append("🔄循環")
                    if _client.auto_recommend.get(guild.id, False):
                        status_parts.append("✨推薦")
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
            for guild in _client.guilds:
                if guild.voice_client and guild.voice_client.playing:
                    current_song = _client.current_songs.get(guild.id)
                    if current_song:
                        await _client.update_presence(current_song.title)
                        await interaction.response.send_message("✅ 已更新音樂機器人狀態顯示", ephemeral=True)
                        return
            await _client.update_presence()
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
        async with aiohttp._clientSession() as session:
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
                "path": "自動推薦",
                "description": "開啟/關閉自動推薦功能",
                "usage": "使用方法: `/自動推薦`",
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