import discord
from core import config, Song , EMBED_COLORS

def create_song_embed(song: Song, position: int) -> discord.Embed:
    platform_info = {
        'youtube': {'color': discord.Color.red(), 'icon': '🎥'},
        'spotify': {'color': discord.Color.green(), 'icon': '🎵'},
    }
    platform_data = platform_info.get(song.platform, {
        'color': discord.Color.default(),
        'icon': '🎵'
    })
    embed = discord.Embed(
        title=f"{platform_data['icon']} 已加入播放清單",
        description=f"[{song.title}]({song.url})",
        color=platform_data['color']
    )
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    minutes = song.duration // 60
    seconds = song.duration % 60
    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
    embed.add_field(name="請求者", value=song.requester.mention, inline=True)
    embed.add_field(name="位置", value=f"#{position}", inline=True)
    embed.add_field(name="平台", value=song.platform.title(), inline=True)
    embed.set_footer(text=f"好聽嗎? • 目前清單長度：{position}")
    return embed

def create_now_playing_embed(song: Song) -> discord.Embed:
    platform_info = {
        'youtube': {'color': EMBED_COLORS['youtube'], 'icon': '🎥'},
        'spotify': {'color': EMBED_COLORS['spotify'], 'icon': '🎵'},
    }
    original_platform = song.platform.lower()
    platform_data = platform_info.get(original_platform, {
        'color': discord.Color.default(),
        'icon': '🎵'
    })
    embed = discord.Embed(
        title=f"{platform_data['icon']} 正在播放",
        description=f"[{song.title}]({song.url})",
        color=platform_data['color']
    )
    embed.set_footer(text="✅可以使用/nowplaymsg開關此訊息")
    if song.thumbnail:
        embed.set_thumbnail(url=song.thumbnail)
    minutes = song.duration // 60
    seconds = song.duration % 60
    embed.add_field(name="長度", value=f"{minutes}:{seconds:02d}", inline=True)
    embed.add_field(name="請求者", value=song.requester.mention, inline=True)
    platform_display_names = {
        'youtube': 'YouTube',
        'spotify': 'Spotify',
    }
    display_platform = platform_display_names.get(original_platform, original_platform.title())
    embed.add_field(name="平台(可能不正常)", value=display_platform, inline=True)
    return embed

def create_error_embed(error_message: str) -> discord.Embed:
    user_name = config["discord_user_name"]
    user_id = int(config["discord_user_id"])
    embed = discord.Embed(
        title="❌ 發生錯誤",
        description=f"{error_message}\n\n如果問題持續發生，請嘗試：\n"
                   f"1️⃣ 使用 `/reload` 重新讓機器人加入\n"
                   f"2️⃣ 重新加入語音頻道\n"
                   f"3️⃣ 聯絡機器人作者 {user_name} <@{user_id}>",
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
        await interaction.followup.send(embed=embed)
        return False
    return True