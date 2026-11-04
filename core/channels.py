import logging
import discord

_channels: dict[int, int] = {}


def remember(guild_id: int, channel_id: int):
    _channels[guild_id] = channel_id


def forget(guild_id: int):
    _channels.pop(guild_id, None)


def resolve(guild: discord.Guild | None):
    if guild is None or guild.me is None:
        return None
    channel_id = _channels.get(guild.id)
    if channel_id is None:
        return None
    channel = guild.get_channel_or_thread(channel_id)
    if channel is None or not hasattr(channel, "send"):
        return None
    perms = channel.permissions_for(guild.me)
    if not perms.view_channel or not perms.send_messages:
        return None
    return channel


async def notify(guild: discord.Guild | None, **kwargs) -> bool:
    channel = resolve(guild)
    if channel is None:
        return False
    try:
        await channel.send(**kwargs)
        return True
    except discord.HTTPException as e:
        logging.warning(f"[Channels] Guild {guild.id}: 發送通知失敗：{e}")
        return False
