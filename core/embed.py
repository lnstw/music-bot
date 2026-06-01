from __future__ import annotations
import discord
import lava_lyra
from discord import ui
from core.player import CustomPlayer
from core.config import check_and_create_config
import logging
import asyncio

_client = None
def set_client_ref(client):
    global _client
    _client = client

EMBED_COLORS = {
    'success': discord.Color.green(),
    'error': discord.Color.red(),
    'info': discord.Color.blue(),
    'warning': discord.Color.yellow(),
    'spotify': discord.Color.from_rgb(30, 215, 96),
    'youtube': discord.Color.from_rgb(255, 0, 0)
}

def create_song_embed(track: lava_lyra.Track, position: int) -> discord.Embed:
    platform_info = {
        'youtube': {'color': discord.Color.red(), 'icon': '🎥'},
        'spotify': {'color': discord.Color.green(), 'icon': '🎵'},
    }
    platform_data = platform_info.get(track._search_type.value.title(), {
        'color': discord.Color.default(),
        'icon': '🎵'
    })
    embed = discord.Embed(
        title=f"{platform_data['icon']} 已加入播放清單",
        description=f"[{track.title}]({track.uri})",
        color=platform_data['color']
    )
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    total_seconds = int(track.length) // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
    requester_str = track.requester.mention if track.requester else "未知用戶"
    embed.add_field(name="請求者", value=requester_str, inline=True)
    embed.add_field(name="位置", value=f"#{position}", inline=True)
    embed.add_field(name="平台", value=track._search_type.value.title(), inline=True)
    embed.set_footer(text=f"好聽嗎? • 目前清單長度：{position}")
    return embed

def create_now_playing_embed(track: lava_lyra.Track) -> discord.Embed:
    platform_info = {
        'youtube': {'color': EMBED_COLORS['youtube'], 'icon': '🎥'},
        'spotify': {'color': EMBED_COLORS['spotify'], 'icon': '🎵'},
    }
    original_platform = track._search_type.value.lower()
    platform_data = platform_info.get(original_platform, {
        'color': discord.Color.default(),
        'icon': '🎵'
    })
    embed = discord.Embed(
        title=f"{platform_data['icon']} 正在播放",
        description=f"[{track.title}]({track.uri})",
        color=platform_data['color']
    )
    embed.set_footer(text="✅可以使用/nowplaymsg開關此訊息")
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    total_seconds = int(track.length) // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
    requester_str = track.requester.mention if track.requester else "未知用戶"
    embed.add_field(name="請求者", value=requester_str, inline=True)
    platform_display_names = {
        'youtube': 'YouTube',
        'spotify': 'Spotify',
    }
    display_platform = platform_display_names.get(original_platform, original_platform.title())
    embed.add_field(name="平台(可能不正常)", value=display_platform, inline=True)
    return embed

def create_error_embed(error_message: str, config: dict = None) -> discord.Embed:
    if config is None and _client:
        config = check_and_create_config()
    
    if config:
        user_name = config.get("discord_user_name", "Bot Author")
        user_id = int(config.get("discord_user_id", "0"))
        description = (f"{error_message}\n\n如果問題持續發生，請嘗試：\n"
                      f"1️⃣ 使用 `/reload` 重新讓機器人加入\n"
                      f"2️⃣ 重新加入語音頻道\n"
                      f"3️⃣ 聯絡機器人作者 {user_name} <@{user_id}>")
    else:
        description = (f"{error_message}\n\n如果問題持續發生，請嘗試：\n"
                      f"1️⃣ 使用 `/reload` 重新讓機器人加入\n"
                      f"2️⃣ 重新加入語音頻道")
    embed = discord.Embed(
        title="❌ 發生錯誤",
        description=description,
        color=EMBED_COLORS['error']
    )
    embed.set_footer(text="機器人錯誤回報")
    return embed

async def check_voice_state_and_respond(interaction: discord.Interaction) -> bool:
    if not interaction.user.voice:
        embed = discord.Embed(
            title="❌ 錯誤",
            description="請先加入語音頻道",
            color=EMBED_COLORS['error']
        )
        await interaction.followup.send(f"{interaction.user.mention}",embed=embed)
        return False
    return True

async def update_embed(target: discord.Message | discord.Interaction, embed: discord.Embed, view: discord.ui.View = None):
    try:
        if isinstance(target, discord.Message):
            try:
                await target.channel.fetch_message(target.id)
            except discord.NotFound:
                logging.warning(f"[update_embed] 訊息已被刪除 (ID: {target.id})")
                return False
            if getattr(view, '_is_v2', False):
                await target.edit(embed=None, view=view)
            else:
                await target.edit(embed=embed, view=view)
            
        elif isinstance(target, discord.Interaction):
            if getattr(view, '_is_v2', False):
                await target.edit_original_response(embed=None, view=view)
            else:
                await target.edit_original_response(embed=embed, view=view)
        return True
    except discord.NotFound:
        logging.warning(f"[update_embed] 訊息不存在")
        return False
    except discord.Forbidden:
        logging.warning(f"[update_embed] 權限不足，無法編輯訊息")
        return False
    except discord.HTTPException as e:
        if e.code == 50027:
            logging.warning(f"[update_embed] Webhook Token 失效，停止更新")
            return False
        logging.warning(f"[update_embed] HTTP 錯誤：{e}")
        return False
    except Exception as e:
        logging.warning(f"[update_embed] 未預期的錯誤：{e}")
        return False
    
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

async def start_auto_update(
    guild_id: int,
    vc: CustomPlayer,
    message: discord.Message,
):
    old_task = _client.auto_update_tasks.get(guild_id) if _client else None
    if old_task and not old_task.done():
        old_task.cancel()
    
    async def auto_update():
        consecutive_errors = 0
        max_consecutive_errors = 3
        try:
            while True:
                try:
                    await asyncio.sleep(20)
                    if not vc or not vc.is_playing:
                        logging.info(f"[AutoUpdate] Guild {guild_id}: 播放已停止")
                        try:
                            await message.edit(view=playend())
                        except (discord.NotFound, discord.Forbidden):
                            pass
                        break
                    song = vc.current
                    if not song:
                        logging.warning(f"[AutoUpdate] Guild {guild_id}: 無法取得目前歌曲")
                        try:
                            await message.edit(view=playend())
                        except (discord.NotFound, discord.Forbidden):
                            pass
                        break
                    from core.view import MusicControlView
                    updated_view = MusicControlView(song, vc)
                    try:
                        await message.edit(view=updated_view)
                        consecutive_errors = 0
                        logging.debug(f"[AutoUpdate] Guild {guild_id}: 成功更新消息")
                    except discord.NotFound:
                        logging.warning(f"[AutoUpdate] Guild {guild_id}: 消息已被刪除")
                        break
                    except discord.Forbidden:
                        logging.warning(f"[AutoUpdate] Guild {guild_id}: 權限不足")
                        break
                        
                except asyncio.CancelledError:
                    logging.info(f"[AutoUpdate] Guild {guild_id}: 任務被取消")
                    break
                except Exception as e:
                    consecutive_errors += 1
                    logging.error(f"[AutoUpdate] Guild {guild_id}: 更新錯誤 ({consecutive_errors}/{max_consecutive_errors})：{e}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logging.error(f"[AutoUpdate] Guild {guild_id}: 達到最大錯誤次數，停止更新")
                        break
                    await asyncio.sleep(5)
                    
        except Exception as e:
            logging.error(f"[AutoUpdate] Guild {guild_id}: 致命錯誤：{e}")
        finally:
            if _client and guild_id in _client.auto_update_tasks:
                del _client.auto_update_tasks[guild_id]
            logging.info(f"[AutoUpdate] Guild {guild_id}: 自動更新任務結束")
    
    task = asyncio.create_task(auto_update())
    if _client:
        _client.auto_update_tasks[guild_id] = task
        logging.info(f"[AutoUpdate] Guild {guild_id}: 開始自動更新任務")