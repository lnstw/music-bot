import asyncio
import json
import logging
from pathlib import Path
import discord

THREAD_NAME = "🎵 音樂播放中"
DELETE_DELAY = 60
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "music_threads.json"

_threads: dict[int, int] = {}
_delete_tasks: dict[int, asyncio.Task] = {}


def _load_records() -> dict[int, int]:
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        return {int(g): int(t) for g, t in data.items()}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.warning(f"[Thread] 讀取討論串紀錄失敗：{e}")
        return {}


def _save_records():
    try:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({str(g): t for g, t in _threads.items()}), encoding="utf-8")
        tmp.replace(DATA_PATH)
    except Exception as e:
        logging.warning(f"[Thread] 寫入討論串紀錄失敗：{e}")


_stale: dict[int, int] = _load_records()


def _track(guild_id: int, thread_id: int):
    _threads[guild_id] = thread_id
    _save_records()


def _untrack(guild_id: int):
    if _threads.pop(guild_id, None) is not None:
        _save_records()


def _can_create_thread(channel, me: discord.Member) -> bool:
    if not isinstance(channel, discord.TextChannel):
        return False
    perms = channel.permissions_for(me)
    return perms.view_channel and perms.create_public_threads and perms.send_messages_in_threads


def _is_music_thread(thread, bot_id: int) -> bool:
    return isinstance(thread, discord.Thread) and thread.owner_id == bot_id and thread.name == THREAD_NAME


async def _remove_thread(thread: discord.Thread, me: discord.Member):
    parent = thread.parent
    if parent is not None and parent.permissions_for(me).manage_threads:
        await thread.delete()
    else:
        await thread.edit(archived=True)


async def get_thread(guild: discord.Guild) -> discord.Thread | None:
    thread_id = _threads.get(guild.id)
    if not thread_id:
        return None
    thread = guild.get_thread(thread_id)
    if thread is None:
        try:
            thread = await guild.fetch_channel(thread_id)
        except (discord.NotFound, discord.Forbidden):
            _untrack(guild.id)
            return None
        except discord.HTTPException:
            return None
    if not isinstance(thread, discord.Thread) or thread.locked:
        _untrack(guild.id)
        return None
    return thread


async def ensure_thread(message: discord.Message | None) -> discord.Thread | None:
    if message is None or message.guild is None or message.guild.me is None:
        return None
    guild = message.guild
    cancel_delete(guild.id)
    thread = await get_thread(guild)
    if thread:
        return thread
    existing = getattr(message, "thread", None)
    if _is_music_thread(existing, guild.me.id) and not existing.locked:
        _track(guild.id, existing.id)
        return existing
    if existing is not None or not _can_create_thread(message.channel, guild.me):
        return None
    try:
        thread = await message.create_thread(name=THREAD_NAME, auto_archive_duration=60)
    except discord.HTTPException as e:
        logging.warning(f"[Thread] Guild {guild.id}: 無法建立討論串：{e}")
        return None
    _track(guild.id, thread.id)
    logging.info(f"[Thread] Guild {guild.id}: 已建立討論串 {thread.id}")
    try:
        embed = discord.Embed(
            description=f"## 停止播放 {DELETE_DELAY} 秒後會自動刪除討論串。\n-# 也可以按下方按鈕立即刪除此討論串。",
            color=discord.Color.blurple()
        )
        await thread.send(embed=embed, view=ThreadDeleteView(), silent=True)
    except discord.HTTPException as e:
        logging.warning(f"[Thread] Guild {guild.id}: 無法發送刪除按鈕：{e}")
    return thread


async def send_notice(interaction: discord.Interaction, embed: discord.Embed | None = None, *, content: str | None = None, view: discord.ui.View | None = None):
    kwargs = {"silent": True}
    if embed is not None:
        kwargs["embed"] = embed
    if view is not None:
        kwargs["view"] = view
    thread = None
    if interaction.guild:
        thread = await ensure_thread(getattr(interaction, "message", None))
    if thread:
        try:
            await thread.send(content, **kwargs)
            return
        except discord.HTTPException as e:
            logging.warning(f"[Thread] Guild {interaction.guild.id}: 發送到討論串失敗：{e}")
    await interaction.followup.send(content, **kwargs)


def cancel_delete(guild_id: int):
    task = _delete_tasks.pop(guild_id, None)
    if task and not task.done():
        task.cancel()


def schedule_delete(guild: discord.Guild | None):
    if guild is None or guild.id not in _threads:
        return
    cancel_delete(guild.id)
    _delete_tasks[guild.id] = asyncio.create_task(_delete_later(guild))


async def _delete_later(guild: discord.Guild):
    try:
        await asyncio.sleep(DELETE_DELAY)
        vc = guild.voice_client
        if vc is not None and getattr(vc, "current", None) is not None:
            return
        thread = await get_thread(guild)
        _untrack(guild.id)
        if thread and guild.me and thread.owner_id == guild.me.id:
            await _remove_thread(thread, guild.me)
            logging.info(f"[Thread] Guild {guild.id}: 播放結束，已移除討論串 {thread.id}")
    except asyncio.CancelledError:
        raise
    except discord.HTTPException as e:
        logging.warning(f"[Thread] Guild {guild.id}: 刪除討論串失敗：{e}")
    finally:
        if _delete_tasks.get(guild.id) is asyncio.current_task():
            _delete_tasks.pop(guild.id, None)


async def _remove_by_id(client: discord.Client, thread_id: int):
    try:
        thread = client.get_channel(thread_id) or await client.fetch_channel(thread_id)
    except (discord.NotFound, discord.Forbidden):
        return
    if _is_music_thread(thread, client.user.id) and thread.guild.me:
        await _remove_thread(thread, thread.guild.me)
        logging.info(f"[Thread] Guild {thread.guild.id}: 已清除殘留討論串 {thread.id}")


async def cleanup_orphan_threads(client: discord.Client):
    in_use = set(_threads.values())
    for thread_id in list(_stale.values()):
        if thread_id in in_use:
            continue
        try:
            await _remove_by_id(client, thread_id)
        except discord.HTTPException as e:
            logging.warning(f"[Thread] 清除殘留討論串 {thread_id} 失敗：{e}")
    _stale.clear()
    _save_records()
    for guild in client.guilds:
        try:
            threads = await guild.active_threads()
        except discord.HTTPException:
            continue
        for thread in threads:
            if _is_music_thread(thread, client.user.id) and thread.id not in in_use:
                try:
                    await _remove_thread(thread, guild.me)
                    logging.info(f"[Thread] Guild {guild.id}: 已清除殘留討論串 {thread.id}")
                except discord.HTTPException:
                    pass


async def remove_all_threads(client: discord.Client):
    for guild_id, thread_id in list(_threads.items()):
        cancel_delete(guild_id)
        try:
            await _remove_by_id(client, thread_id)
        except discord.HTTPException as e:
            logging.warning(f"[Thread] 關機時刪除討論串 {thread_id} 失敗：{e}")
        else:
            _untrack(guild_id)


class ThreadDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="刪除此討論串", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="music_thread:delete")
    async def delete_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        thread = interaction.channel
        me = interaction.guild.me if interaction.guild else None
        if me is None or not _is_music_thread(thread, me.id):
            await interaction.response.send_message("❌ 這不是機器人建立的音樂討論串", ephemeral=True)
            return
        member = interaction.user
        vc = interaction.guild.voice_client
        allowed = (
            thread.permissions_for(member).manage_threads
            or vc is None
            or (member.voice is not None and member.voice.channel == vc.channel)
        )
        if not allowed:
            await interaction.response.send_message("❌ 你需要在機器人所在的語音頻道才能刪除討論串", ephemeral=True)
            return
        await interaction.response.send_message("🗑️ 正在刪除討論串...", ephemeral=True)
        if _threads.get(interaction.guild.id) == thread.id:
            cancel_delete(interaction.guild.id)
            _untrack(interaction.guild.id)
        try:
            await _remove_thread(thread, me)
            logging.info(f"[Thread] Guild {interaction.guild.id}: {member} 手動刪除討論串 {thread.id}")
        except discord.HTTPException as e:
            logging.warning(f"[Thread] Guild {interaction.guild.id}: 手動刪除討論串失敗：{e}")
            try:
                await interaction.followup.send(f"❌ 刪除失敗：{e}", ephemeral=True)
            except discord.HTTPException:
                pass
