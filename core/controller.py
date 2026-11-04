import logging
import discord
from core.player import CustomPlayer
from core.thread import set_active_controller, get_active_controller
from core.embed import start_auto_update


def _partial(guild: discord.Guild, ref: tuple[int, int]):
    channel = guild.get_channel_or_thread(ref[0])
    if channel is None or not hasattr(channel, "get_partial_message"):
        return None
    return channel.get_partial_message(ref[1])


async def _supersede(guild: discord.Guild, ref: tuple[int, int]):
    from core.view import SupersededView
    message = _partial(guild, ref)
    if message is None:
        return
    try:
        await message.edit(view=SupersededView())
    except discord.HTTPException as e:
        logging.warning(f"[Controller] Guild {guild.id}: 無法使舊控制器失效：{e}")


async def send_controller(interaction, player: CustomPlayer, *, silent: bool = True):
    from core.view import MusicControlView
    track = player.current
    if track is None or interaction.guild is None:
        return None
    sent = await interaction.followup.send(view=MusicControlView(track, player), silent=silent)
    message = sent
    try:
        message = interaction.channel.get_partial_message(sent.id)
    except Exception:
        pass
    guild = interaction.guild
    old = await set_active_controller(guild, message)
    if old is not None:
        await _supersede(guild, old)
    await start_auto_update(guild.id, player, message)
    return message


async def refresh_controller(player: CustomPlayer):
    from core.view import MusicControlView
    guild = player.guild
    ref = get_active_controller(guild.id)
    if ref is None or player.current is None:
        return
    message = _partial(guild, ref)
    if message is None:
        return
    try:
        await message.edit(view=MusicControlView(player.current, player))
    except discord.HTTPException as e:
        logging.warning(f"[Controller] Guild {guild.id}: 更新控制器失敗：{e}")


async def end_controller(guild: discord.Guild):
    from core.view import playend
    ref = get_active_controller(guild.id)
    if ref is None:
        return
    message = _partial(guild, ref)
    if message is None:
        return
    try:
        await message.edit(view=playend())
    except discord.HTTPException:
        pass
