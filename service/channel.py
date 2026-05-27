import discord

_client = None
def set_client_ref(client):
    global _client
    _client = client

async def send_message_to_last_channel(guild_id: int, message: str = None, embed: discord.Embed = None):
    if guild_id in _client.last_channels:
        guild = _client.get_guild(guild_id)
        if guild:
            channel = guild.get_channel(_client.last_channels[guild_id])
            if channel:
                try:
                    if embed:
                        await channel.send(embed=embed, silent=True)
                    elif message:
                        await channel.send(message, silent=True)
                except Exception as e:
                    print(f"發送訊息時發生錯誤: {e}")