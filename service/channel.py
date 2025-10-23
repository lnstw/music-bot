import discord
from core import MusicClient

async def send_message_to_last_channel(client: MusicClient, guild_id: int, message: str = None, embed: discord.Embed = None):
    if guild_id in client.last_channels:
        guild = client.get_guild(guild_id)
        if guild:
            channel = guild.get_channel(client.last_channels[guild_id])
            if channel:
                try:
                    if embed:
                        await channel.send(embed=embed, silent=True)
                    elif message:
                        await channel.send(message, silent=True)
                except Exception as e:
                    print(f"發送訊息時發生錯誤: {e}")