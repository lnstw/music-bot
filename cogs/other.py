import discord
from discord import app_commands
from discord.ext import commands
import wavelink

from service.embed import check_voice_state_and_respond, EMBED_COLORS
from service.view import CategorySelectView

class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_client(self):
        return self.bot
    
    
    @app_commands.command(name="help", description="顯示指令說明")
    async def help(self, interaction: discord.Interaction):
        view = CategorySelectView()
        embed = discord.Embed(
            title="📚 命令幫助",
            description="請從下方選單選擇一個分類以查看相關命令",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, view=view)


    @app_commands.command(name="ping", description="檢查機器人延遲")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! 延遲: {self.bot.latency*1000:.2f}ms")
    
    @app_commands.command(name="邀請機器人", description="獲取機器人邀請連結")
    async def slash_command(self, interaction: discord.Interaction):
        invite_bot = discord.ui.View()
        invite_bot.add_item(discord.ui.Button(label="邀請我", style=discord.ButtonStyle.success, url="https://discord.com/oauth2/authorize?client_id=1269984207501787177"))
        await interaction.response.send_message("點下面的按鈕邀請我AAAAAA", view=invite_bot)
        
    @app_commands.command(name="自動推薦", description="開啟/關閉自動推薦功能")
    async def autorecommend(self, interaction: discord.Interaction):
        client = self.get_client()
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        guild_id = interaction.guild_id
        if guild_id not in client.auto_recommend:
            client.auto_recommend[guild_id] = False
        client.auto_recommend[guild_id] = not client.auto_recommend[guild_id]
        status = "開啟" if client.auto_recommend[guild_id] else "關閉"
        embed = discord.Embed(
            title="✨ 自動推薦設置",
            description=f"自動推薦功能已{status}",
            color=EMBED_COLORS['success']
        )
        embed.set_footer(text="當播放清單為空時，將自動添加相似歌曲")
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="現正播放訊息", description="開啟/關閉目前歌曲的提示訊息")
    async def nowplaymsg(self, interaction: discord.Interaction):
        client = self.get_client()
        guild_id = interaction.guild_id
        if guild_id not in client.show_now_song:
            client.show_now_song[guild_id] = False
        client.show_now_song[guild_id] = not client.show_now_song[guild_id]
        status = "開啟" if client.show_now_song[guild_id] else "關閉"
        if client.show_now_song[guild_id]:
            embed_color = EMBED_COLORS['success']
            embed = discord.Embed(
                title="⚙️ 播放提示設置",
                description=f"下一首歌曲提示已{status}",
                color=embed_color
            )
            embed.add_field(
                name="目前設定", 
                value="將在播放前發送目前歌曲的提示訊息",
                inline=False
            )
            embed.set_footer(text="✅預設開啟")
        else:
            embed_color = EMBED_COLORS['error']
            embed = discord.Embed(
                title="⚙️ 播放提示設置",
                description=f"下一首歌曲提示已{status}",
                color=embed_color
            )
            embed.add_field(
                name="目前設定",
                value="已關閉發送目前歌曲的提示訊息",
                inline=False
            )
            embed.set_footer(text="✅預設開啟")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="停止", description="停止播放並清空播放清單")
    async def stop(self, interaction: discord.Interaction):
        client = self.get_client()
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        vc: wavelink.Player = interaction.guild.voice_client
        guild_id = interaction.guild_id
        if not hasattr(client, "force_stop"):
            client.force_stop = {}
        client.force_stop[guild_id] = True
        if vc.playing:
            await vc.stop()
        if guild_id in client.queues:
            client.queues[guild_id].clear()
        if guild_id in client.current_songs:
            del client.current_songs[guild_id]
        if guild_id in client.loop_mode:
            client.loop_mode[guild_id] = False
        if guild_id in client.auto_recommend:
            client.auto_recommend[guild_id] = False
        vc.queue.clear()
        await client.update_presence()
        embed = discord.Embed(
            title="⏹️ 已停止播放",
            description="已清空播放清單並關閉循環模式",
            color=EMBED_COLORS['success']
        )
        if guild_id in client.auto_recommend and client.auto_recommend[guild_id]:
            embed.set_footer(text="自動推薦功能仍然開啟")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Other(bot))