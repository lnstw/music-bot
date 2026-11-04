import discord
from discord.ui import Button , View
from discord.ext import commands
from discord import ui
import lava_lyra
import asyncio
import datetime
import aiohttp
from io import BytesIO
import requests
from PIL import Image
import colorsys
from core.embed import create_error_embed, check_voice_state_and_respond, EMBED_COLORS
from core.player import CustomPlayer
from core.thread import send_notice, schedule_delete, is_active_controller
import logging


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

        if player.paused:
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

    async def _guard(self, interaction: discord.Interaction) -> bool:
        await interaction.response.defer()
        guild = interaction.guild
        message = interaction.message
        if guild is None or message is None or not is_active_controller(guild.id, message.id):
            try:
                await interaction.edit_original_response(view=SupersededView())
            except discord.HTTPException:
                pass
            return False
        return True

    async def _get_player(self, interaction: discord.Interaction) -> CustomPlayer | None:
        player = None
        for attempt in range(3):
            player = interaction.guild.voice_client
            if isinstance(player, CustomPlayer) and player.current:
                return player
            if attempt < 2:
                await asyncio.sleep(1)
        await interaction.edit_original_response(view=playend())
        return None

    async def _prepare(self, interaction: discord.Interaction, *, voice: bool = True) -> CustomPlayer | None:
        if not await self._guard(interaction):
            return None
        if voice and not await check_voice_state_and_respond(interaction):
            return None
        return await self._get_player(interaction)

    async def _redraw(self, interaction: discord.Interaction, player: CustomPlayer):
        song = player.current if player else None
        view = MusicControlView(song, player) if song else playend()
        await interaction.edit_original_response(view=view)

    async def next_play(self, interaction: discord.Interaction):
        player = await self._prepare(interaction)
        if not player:
            return
        next_track = player.queue.peek_upcoming()
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
        await player.skip()
        if not player.current:
            schedule_delete(interaction.guild)
        await self._redraw(interaction, player)
        await send_notice(interaction, embed)

    async def play_pause(self, interaction: discord.Interaction):
        player = await self._prepare(interaction)
        if not player:
            return
        if player.paused:
            await player.apply_pause(False)
            embed = discord.Embed(
                title="▶️ 已恢復播放",
                color=EMBED_COLORS['success']
            )
        else:
            await player.apply_pause(True)
            embed = discord.Embed(
                title="⏸️ 已暫停播放",
                color=EMBED_COLORS['success']
            )
        await self._redraw(interaction, player)
        await send_notice(interaction, embed)

    async def toggle_loop(self, interaction: discord.Interaction):
        player = await self._prepare(interaction)
        if not player:
            return
        status = "開啟" if player.toggle_loop() else "關閉"
        await self._redraw(interaction, player)
        embed = discord.Embed(
            title="🔁 循環模式設置",
            description=f"播放清單循環模式已{status}",
            color=EMBED_COLORS['success']
        )
        await send_notice(interaction, embed)

    async def show_queue(self, interaction: discord.Interaction):
        try:
            if not await self._guard(interaction):
                return
            player: CustomPlayer = interaction.guild.voice_client
            if not player:
                await send_notice(interaction, content="❌ 機器人不在語音頻道中！")
                return
            queue_list = player.queue.upcoming()
            current_song = player.current
            status_parts = []
            if player.queue.is_looping:
                status_parts.append("🔄 循環模式：開啟")
            paginator = QueuePaginator(interaction, queue_list, songs_per_page=10, current_song=current_song, status_parts=status_parts)
            await send_notice(interaction, view=paginator)
        except Exception as e:
            logging.error(f"顯示播放清單時發生錯誤：{str(e)}")
            error_embed = create_error_embed(f"顯示播放清單時發生錯誤：{str(e)}")
            await send_notice(interaction, error_embed)

    async def shuffle_queue(self, interaction: discord.Interaction):
        if not await self._guard(interaction):
            return
        if not await check_voice_state_and_respond(interaction):
            return
        player: CustomPlayer = interaction.guild.voice_client
        if not player or not player.queue.upcoming():
            await send_notice(interaction, content="❌ 播放清單是空的！")
            return
        player.queue.shuffle_upcoming()

        embed = discord.Embed(
            title="🔀 已打亂播放清單",
            color=EMBED_COLORS['success']
        )
        await send_notice(interaction, embed)

    async def Rewind(self, interaction: discord.Interaction):
        player = await self._prepare(interaction)
        if not player:
            return
        new_position = max(int(player.position) - 10000, 0)
        await player.seek(new_position)
        embed = discord.Embed(
            title="⏪ 已倒轉 10 秒",
            color=EMBED_COLORS['success']
        )
        await self._redraw(interaction, player)
        await send_notice(interaction, embed)

    async def forward(self, interaction: discord.Interaction):
        player = await self._prepare(interaction)
        if not player:
            return
        song = player.current
        new_position = min(int(player.position) + 10000, max(int(song.length) - 1000, 0))
        await player.seek(new_position)
        embed = discord.Embed(
            title="⏩ 已快轉 10 秒",
            color=EMBED_COLORS['success']
        )
        await self._redraw(interaction, player)
        await send_notice(interaction, embed)

    async def _change_volume(self, interaction: discord.Interaction, delta: int):
        player = await self._prepare(interaction)
        if not player:
            return
        new_volume = max(0, min(player.volume + delta, 150))
        await player.set_volume(new_volume)
        embed = discord.Embed(
            title="🔊 音量增加" if delta > 0 else "🔊 音量減少",
            description=f"音量已設置為 {new_volume}%",
            color=EMBED_COLORS['success']
        )
        await self._redraw(interaction, player)
        await send_notice(interaction, embed)

    async def increase_volume(self, interaction: discord.Interaction):
        await self._change_volume(interaction, 5)

    async def decrease_volume(self, interaction: discord.Interaction):
        await self._change_volume(interaction, -5)

    async def update_status(self, interaction: discord.Interaction):
        player = await self._prepare(interaction, voice=False)
        if not player:
            return
        await self._redraw(interaction, player)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        logging.error(f"控制器按鈕發生錯誤：{error!r}", exc_info=error)
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

class SupersededView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        text_content = "# ⚠️ 此控制器已失效\n\n### 已有更新的控制器，請使用最下方的控制器。"
        self.text_display = ui.TextDisplay(text_content)
        container = ui.Container(
            self.text_display,
            accent_color=discord.Color.light_grey()
        )
        self.add_item(container)

def expired_embed() -> discord.Embed:
    return discord.Embed(
        title="⚠️ 過期的物件",
        description="此互動已過期或已失效，請重新使用指令取得。",
        color=discord.Color.yellow(),
    )

class ExpiredView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.text_display = ui.TextDisplay("# ⚠️ 過期的物件"+chr(10)+chr(10)+"### 此互動已過期或已失效，請重新使用指令取得。")
        self.add_item(ui.Container(self.text_display, accent_color=discord.Color.yellow()))

class timeout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        text_content = "# ⚠️ 按鈕已失效\n\n### 此互動已失敗或已過期，請重新使用 /音樂 控制器 取得新的控制面板。"
        self.text_display = ui.TextDisplay(text_content)
        container = ui.Container(
            self.text_display, 
            accent_color=discord.Color.yellow()
        )
        self.add_item(container)

def _fmt_duration(length_ms) -> str:
    sec = int(length_ms / 1000) if length_ms else 0
    return f"{sec // 60}:{sec % 60:02d}"

class SimpleView(discord.ui.LayoutView):
    def __init__(self, text: str, color: discord.Color = None):
        super().__init__(timeout=None)
        self.add_item(ui.Container(ui.TextDisplay(text), accent_color=color or EMBED_COLORS['info']))

class PagedButton(discord.ui.Button):
    def __init__(self, label: str, step: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.step = step
    async def callback(self, interaction: discord.Interaction):
        await self.view.turn(interaction, self.step)

class QueuePaginator(discord.ui.LayoutView):
    def __init__(self, interaction, queue_list, songs_per_page=10, current_song=None, status_parts=None):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.queue_list: list[lava_lyra.Track] = queue_list
        self.current_song: lava_lyra.Track | None = current_song
        self.status_parts = status_parts or []
        self.page = 0
        self.songs_per_page = songs_per_page
        self.page_ranges = self._calculate_pages()
        self.total_pages = len(self.page_ranges) or 1
        self._render()

    def _line(self, idx: int) -> str:
        song = self.queue_list[idx]
        title = song.title[:50] + "..." if len(song.title) > 50 else song.title
        return f"`{idx+1}.` [{title}]({song.uri}) | `{_fmt_duration(song.length)}`\n"

    def _calculate_pages(self) -> list[tuple[int, int]]:
        pages = []
        start_idx = 0
        total_songs = len(self.queue_list)
        while start_idx < total_songs:
            current_length = 0
            end_idx = start_idx
            while end_idx < total_songs and (end_idx - start_idx) < self.songs_per_page:
                line = self._line(end_idx)
                if current_length + len(line) > 950:
                    break
                current_length += len(line)
                end_idx += 1
            if end_idx == start_idx:
                end_idx += 1
            pages.append((start_idx, end_idx))
            start_idx = end_idx
        return pages

    def _text(self) -> str:
        parts = [f"# 📃 播放清單 (第 {self.page+1}/{self.total_pages} 頁)"]
        if self.status_parts:
            parts.append(" | ".join(self.status_parts))
        if self.current_song:
            requester = self.current_song.requester.mention if self.current_song.requester else "未知用戶"
            parts.append(f"### 🎵 正在播放\n[{self.current_song.title}]({self.current_song.uri})\n`{_fmt_duration(self.current_song.length)}` | {requester}")
        description = ""
        display_start = display_end = 0
        if self.page_ranges and self.page < len(self.page_ranges):
            start_idx, end_idx = self.page_ranges[self.page]
            display_start, display_end = start_idx + 1, end_idx
            description = "".join(self._line(i) for i in range(start_idx, end_idx))
            if (end_idx - start_idx) < self.songs_per_page and end_idx < len(self.queue_list):
                description += "-# 翻頁後還有更多歌曲..."
        if not description:
            description = "播放清單是空的"
        parts.append(f"### 📋 待播清單 ({display_start}-{display_end}/{len(self.queue_list)})\n{description}")
        if self.queue_list:
            total = int(sum(s.length for s in self.queue_list) / 1000)
            h, m, s = total // 3600, (total % 3600) // 60, total % 60
            parts.append(f"-# 總時長: {h}:{m:02d}:{s:02d}" if h > 0 else f"-# 總時長: {m:02d}:{s:02d}")
        return "\n\n".join(parts)

    def _render(self):
        self.clear_items()
        prev_button = PagedButton("上一頁", -1)
        next_button = PagedButton("下一頁", 1)
        prev_button.disabled = self.page == 0
        next_button.disabled = self.page >= self.total_pages - 1
        self.add_item(ui.Container(ui.TextDisplay(self._text()), ui.ActionRow(prev_button, next_button), accent_color=EMBED_COLORS['info']))

    async def turn(self, interaction: discord.Interaction, step: int):
        new_page = self.page + step
        if 0 <= new_page < self.total_pages:
            self.page = new_page
            self._render()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

class OpSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, custom_options: list = None, placeholder: str = "選擇功能"):
        if not custom_options:
            custom_options = [
                discord.SelectOption(label="Lavalink 播放狀態", value="Lavalink 播放狀態"),
                discord.SelectOption(label="更新機器人狀態", value="更新機器人狀態"),
            ]
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=custom_options,
            custom_id="persistent_view:op_select"
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.bot.config.get("discord_user_id")).strip('"') and not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("❌ 你沒有權限使用此功能", ephemeral=True)
            return
        op_select = self.values[0]
        if op_select == "Lavalink 播放狀態":
            pages = []
            for guild in self.bot.guilds:
                if guild.voice_client and isinstance(guild.voice_client, CustomPlayer) and guild.voice_client.is_playing:
                    player: CustomPlayer = guild.voice_client
                    current_song = player.current
                    voice_channel = player.channel
                    member_count = len([m for m in voice_channel.members if not m.bot])
                    status = "🔄循環" if player.queue.is_looping else "➡️ 一般播放"
                    pages.append(
                        f"# 🎵 Lavalink 播放狀態\n📡 {guild.name}\n\n"
                        f"**🎵 播放中**\n{current_song.title if current_song else '未知'}\n\n"
                        f"**👥 頻道**: {voice_channel.name} ({member_count}人在線)\n"
                        f"**📋 佇列**: {len(player.queue.upcoming())} 首\n"
                        f"**⚙️ 狀態**: {status}"
                    )
            if not pages:
                await interaction.response.send_message(view=SimpleView("# 🎵 Lavalink 播放狀態\n目前沒有伺服器正在播放音樂"), ephemeral=True)
            else:
                await interaction.response.send_message(view=LavalinkStatusView(pages), ephemeral=True)
        if op_select == "更新機器人狀態":
            await self.bot.auto_update_status()
            await interaction.response.send_message(view=SimpleView("✅ 已更新音樂機器人狀態顯示", EMBED_COLORS['success']), ephemeral=True)

class opselect_view(discord.ui.LayoutView):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.add_item(ui.Container(ui.TextDisplay("請選擇功能"), ui.ActionRow(OpSelect(bot=bot)), accent_color=EMBED_COLORS['info']))

class LavalinkStatusView(discord.ui.LayoutView):
    def __init__(self, pages: list[str]):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = 0
        self._render()

    def _render(self):
        self.clear_items()
        prev_button = PagedButton("⬅️ 上一頁", -1)
        next_button = PagedButton("➡️ 下一頁", 1)
        prev_button.disabled = self.current_page == 0
        next_button.disabled = self.current_page >= len(self.pages) - 1
        footer = f"-# 第 {self.current_page + 1} / {len(self.pages)} 頁｜總計 {len(self.pages)} 個伺服器正在播放"
        self.add_item(ui.Container(ui.TextDisplay(f"{self.pages[self.current_page]}\n\n{footer}"), ui.ActionRow(prev_button, next_button), accent_color=EMBED_COLORS['info']))

    async def turn(self, interaction: discord.Interaction, step: int):
        new_page = self.current_page + step
        if 0 <= new_page < len(self.pages):
            self.current_page = new_page
            self._render()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

class RefreshActionRow(ui.ActionRow):
    @discord.ui.button(label="重新取得", style=discord.ButtonStyle.primary, custom_id="refresh_button")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=SimpleView("<a:loading:1429472831103832195> 重新取得中...", discord.Color.yellow()))
        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.redbean0721.com/api/img?type=json") as api_response:
                end_time = datetime.datetime.now()
                if api_response.status != 200:
                    await interaction.edit_original_response(view=SimpleView("無法獲取圖片，請稍後再試。", EMBED_COLORS['error']))
                    return
                data = await api_response.json()
                image_url = data.get("url")
                tag = data.get("tag")
                color_task = asyncio.create_task(get_dominant_color(image_url))
                image_response = await session.get(image_url)
                image_bytes = await image_response.read()
                embed_color = await color_task
                elapsed = (end_time - start_time).total_seconds()
                file = discord.File(BytesIO(image_bytes), filename="image.jpg")
                view = RefreshButton(image_url=image_url, tag=tag, elapsed=elapsed, color=embed_color)
                await interaction.edit_original_response(view=view, attachments=[file])

class RefreshButton(discord.ui.LayoutView):
    def __init__(self, image_url: str = None, tag: str = None, elapsed: float = None, color: discord.Color = None):
        super().__init__(timeout=None)
        items = []
        if image_url:
            items.append(ui.TextDisplay(f"## 隨機圖\n提示詞: {tag}"))
            items.append(ui.MediaGallery(discord.MediaGalleryItem("attachment://image.jpg")))
            if elapsed is not None:
                items.append(ui.TextDisplay(f"-# 回應時間: {elapsed:.2f}s"))
        else:
            items.append(ui.TextDisplay("## 隨機圖"))
        row = RefreshActionRow()
        if image_url:
            row.add_item(discord.ui.Button(label="點我跳轉", url=image_url, style=discord.ButtonStyle.link))
        items.append(row)
        self.add_item(ui.Container(*items, accent_color=color or EMBED_COLORS['info']))

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
                "usage": "使用方法: `/音樂 循環`",
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
                "path": "隨機圖",
                "description": "可以隨機給你一張圖片",
                "usage": "使用方法: `/隨機圖`",
            },
            {
                "path": "停止",
                "description": "停止機器人並清空播放清單",
                "usage": "使用方法: `/停止`",
            }

        ],
    }
}

PREFIX_USAGE = {
    "音樂 播放": "`p!play <歌名/連結>`（別名 `p!p`）",
    "音樂 暫停": "`p!pause`",
    "音樂 繼續": "`p!resume`（別名 `p!r`）",
    "音樂 跳過": "`p!skip`（別名 `p!s`、`p!next`）",
    "音樂 音量": "`p!volume <0-150>`（別名 `p!vol`、`p!v`）",
    "音樂 控制器": "`p!controller`（別名 `p!np`、`p!c`）",
    "音樂 循環": "`p!loop`（別名 `p!l`）",
    "播放清單 顯示": "`p!queue`（別名 `p!q`）",
    "播放清單 清空": "`p!clear`",
    "播放清單 移除": "`p!remove <位置>`（別名 `p!rm`）",
    "播放清單 隨機": "`p!shuffle`（別名 `p!sh`）",
    "播放清單 插入": "`p!insert <歌名/連結>`（別名 `p!i`、`p!pn`）",
    "機器人 離開": "`p!leave`（別名 `p!dc`）",
    "ping": "`p!ping`",
    "停止": "`p!stop`",
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


class HelpView(discord.ui.LayoutView):
    def __init__(self, author_id: int, mode: str = "slash"):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.mode = mode
        self.category: str | None = None
        self.command: str | None = None
        self.command_ids: dict | None = None
        self.message = None
        self._render()

    def _label(self, path: str) -> str:
        if self.mode == "prefix":
            return PREFIX_USAGE[path].split("`")[1]
        return f"/{path}"

    def _commands(self) -> list[dict]:
        commands_info = HELP_CATEGORIES[self.category]["commands"]
        if self.mode == "prefix":
            return [c for c in commands_info if c["path"] in PREFIX_USAGE]
        return commands_info

    def _render(self):
        self.clear_items()
        other = "slash" if self.mode == "prefix" else "p!"
        if self.category is None:
            title = "# 📚 p! 指令" if self.mode == "prefix" else "# 📚 命令幫助"
            text = f"{title}\n請從下方選單選擇一個分類以查看相關命令\n-# 也可以使用 {'/help' if self.mode == 'prefix' else 'p!help'} 查看 {other} 指令"
            select = discord.ui.Select(
                placeholder="選擇一個分類...",
                options=[discord.SelectOption(label=data["title"], value=key) for key, data in HELP_CATEGORIES.items()],
            )
            select.callback = self._on_category
            items = [discord.ui.TextDisplay(text), discord.ui.ActionRow(select)]
            color = discord.Color.green()
        elif self.command is None:
            data = HELP_CATEGORIES[self.category]
            select = discord.ui.Select(
                placeholder="選擇一個命令...",
                options=[
                    discord.SelectOption(label=self._label(c["path"])[:100], description=c["description"][:100], value=c["path"])
                    for c in self._commands()
                ],
            )
            select.callback = self._on_command
            back = discord.ui.Button(label="返回分類選擇", emoji="◀️", style=discord.ButtonStyle.gray)
            back.callback = self._on_home
            items = [
                discord.ui.TextDisplay(f"# {data['title']}\n請從下方選單選擇一個命令以查看詳細資訊"),
                discord.ui.ActionRow(select),
                discord.ui.ActionRow(back),
            ]
            color = discord.Color.blue()
        else:
            info = next(c for c in HELP_CATEGORIES[self.category]["commands"] if c["path"] == self.command)
            if self.mode == "prefix":
                body = f"# {self._label(self.command)}\n**說明:**\n{info['description']}\n\n**用法:** {PREFIX_USAGE[self.command]}\n**Slash 指令:** `/{self.command}`"
            else:
                cmd_id = (self.command_ids or {}).get(self.command)
                title = f"</{self.command}:{cmd_id}>" if cmd_id else f"/{self.command}"
                body = f"# {title}\n**說明:**\n{info['description']}\n\n**{info['usage']}**"
                if self.command in PREFIX_USAGE:
                    body += f"\n\n**前綴指令:** {PREFIX_USAGE[self.command]}"
            back_category = discord.ui.Button(label=f"返回 {HELP_CATEGORIES[self.category]['title']}", emoji="◀️", style=discord.ButtonStyle.primary)
            back_category.callback = self._on_back_category
            back_home = discord.ui.Button(label="回到最前面", emoji="🏠", style=discord.ButtonStyle.gray)
            back_home.callback = self._on_home
            items = [discord.ui.TextDisplay(body), discord.ui.ActionRow(back_category, back_home)]
            color = discord.Color.green()
        self.add_item(discord.ui.Container(*items, accent_color=color))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ 這是別人叫出的說明，請自己使用 `/help` 或 `p!help`", ephemeral=True)
            return False
        return True

    async def _on_category(self, interaction: discord.Interaction):
        self.category = interaction.data["values"][0]
        self.command = None
        self._render()
        await interaction.response.edit_message(view=self)

    async def _on_command(self, interaction: discord.Interaction):
        self.command = interaction.data["values"][0]
        if self.mode == "slash" and self.command_ids is None:
            try:
                self.command_ids = build_command_id_lookup(await interaction.client.tree.fetch_commands())
            except Exception:
                self.command_ids = {}
        self._render()
        await interaction.response.edit_message(view=self)

    async def _on_back_category(self, interaction: discord.Interaction):
        self.command = None
        self._render()
        await interaction.response.edit_message(view=self)

    async def _on_home(self, interaction: discord.Interaction):
        self.category = None
        self.command = None
        self._render()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=ExpiredView())
            except discord.HTTPException:
                pass
