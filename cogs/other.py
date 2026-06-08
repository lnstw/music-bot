import discord
from discord import app_commands
from discord.ext import commands
from core.embed import check_voice_state_and_respond, EMBED_COLORS
from core.view import CategorySelectView
from core.player import CustomPlayer


class Other(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
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
        invite_bot.add_item(discord.ui.Button(label="邀請我", style=discord.ButtonStyle.success, url=f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}"))
        await interaction.response.send_message("點下面的按鈕邀請我AAAAAA", view=invite_bot)
    
    @app_commands.command(name="停止", description="停止播放並清空播放清單")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await check_voice_state_and_respond(interaction):
                return
        if not interaction.guild.voice_client:
            await interaction.followup.send("❌ 沒有歌曲正在播放！")
            return
        player: CustomPlayer = interaction.guild.voice_client
        
        if player.is_playing:
            await player.set_pause(True)
        player.queue.clear()
        embed = discord.Embed(
            title="⏹️ 已停止播放",
            description="已清空播放清單並關閉循環模式",
            color=EMBED_COLORS['success']
        )
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Other(bot))