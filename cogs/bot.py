import discord
from discord import app_commands
from discord.ext import commands
import lava_lyra
from collections import deque
import asyncio
from typing import cast

from core.embed import create_error_embed, EMBED_COLORS, check_voice_state_and_respond
from core.player import CustomPlayer


class botcommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    bc = app_commands.Group(name="機器人", description="機器人相關指令")
    
    
    #==離開語音頻道==
    @bc.command(name="離開", description="讓機器人離開語音頻道")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.user.guild_permissions.move_members:
            if not await check_voice_state_and_respond(interaction):
                return
        else:
            pass
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 機器人不在語音頻道中！")
            return
        vc: CustomPlayer = interaction.guild.voice_client
        await vc.destroy()
        await interaction.followup.send("👋 已離開語音頻道")
    #==重新載入==
    # @bc.command(name="重載", description="重新載入音樂播放 (重新連接機器人)")
    # async def reload(self, interaction: discord.Interaction):
    #     try:
    #         await interaction.response.defer()
    #         if not await check_voice_state_and_respond(interaction):
    #             return
    #         current_channel = interaction.user.voice.channel
    #         current_queue = None
    #         current_song = None
    #         current_position = 0
    #         # loop_status = client.loop_mode.get(guild_id, False)
    #         # volume = client.default_volume
    #         player = cast(CustomPlayer, interaction.guild.voice_client)
    #         if player.is_playing:
                
    #             if player:
    #                 current_position = int(player.length)
    #         current_queue = player.queue.get_queue
    #         current_song = player.current
    #         if interaction.guild.voice_client:
    #             try:
    #                 player: wavelink.player = interaction.guild.voice_client
    #                 await player.disconnect()
    #                 await asyncio.sleep(1)
    #             except Exception as e:
    #                 print(f"斷開連接時發生錯誤：{e}")
    #         try:
    #             player: wavelink.Player = await current_channel.connect(cls=LavalinkPlayerCompat)
    #             await player.set_volume(volume)
    #             if current_queue:
    #                 client.queues[guild_id] = deque(current_queue)
    #             if current_song:
    #                 client.current_songs[guild_id] = current_song
    #             client.loop_mode[guild_id] = loop_status
    #             client.auto_recommend[guild_id] = auto_recommend_status
    #             if current_song:
    #                 try:
    #                     tracks = await wavelink.Playable.search(current_song.url)
    #                     if tracks:
    #                         track = tracks[0]
    #                         await player.play(track)
    #                         if current_position > 0:
    #                             await asyncio.sleep(0.5)
    #                             await player.seek(current_position)
    #                         embed = discord.Embed(
    #                             title="✅ 重新載入成功",
    #                             description=f"已恢復播放：[{current_song.title}]({current_song.url})",
    #                             color=EMBED_COLORS['success']
    #                         )
    #                         embed.add_field(
    #                             name="播放進度", 
    #                             value=f"{current_position//1000//60}:{(current_position//1000)%60:02d}",
    #                             inline=True
    #                         )
    #                         if current_queue:
    #                             embed.add_field(
    #                                 name="佇列歌曲數", 
    #                                 value=str(len(current_queue)),
    #                                 inline=True
    #                             )
    #                         embed.add_field(
    #                             name="循環模式", 
    #                             value="開啟" if loop_status else "關閉",
    #                             inline=True
    #                         )
    #                         embed.add_field(
    #                             name="音量", 
    #                             value=volume,
    #                             inline=True
    #                         )
    #                 except Exception as e:
    #                     print(f"恢復播放時發生錯誤：{e}")
    #                     await play_next(guild=interaction.guild, vc=player, client=client)
    #                     embed = discord.Embed(
    #                         title="⚠️ 部分重新載入成功",
    #                         description="無法恢復當前歌曲的播放進度，已開始播放下一首",
    #                         color=EMBED_COLORS['warning']
    #                     )
    #             else:
    #                 embed = discord.Embed(
    #                     title="✅ 重新載入成功",
    #                     description="已重新連接到語音頻道",
    #                     color=EMBED_COLORS['success']
    #                 )
    #             await interaction.followup.send(embed=embed)
    #         except Exception as e:
    #             print(f"重新連接時發生錯誤：{e}")
    #             error_embed = create_error_embed(
    #                 f"重新連接時發生錯誤：{str(e)}\n"
    #                 "請確保：\n"
    #                 "1. 機器人有權限加入該語音頻道\n"
    #                 "2. 語音頻道未滿\n"
    #                 "3. 網路連接正常"
    #             )
    #             await interaction.followup.send(embed=error_embed)
    #     except Exception as e:
    #         print(f"重新載入時發生錯誤：{str(e)}")
    #         error_embed = create_error_embed(f"重新載入時發生錯誤：{str(e)}")
    #         await interaction.followup.send(embed=error_embed)

async def setup(bot):
    await bot.add_cog(botcommand(bot))