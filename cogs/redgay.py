import discord
from discord import app_commands
from discord.ext import commands
from core.embed import EMBED_COLORS
import aiohttp
import datetime
from datetime import timedelta
from io import BytesIO
import asyncio

from core.view import get_dominant_color, RefreshButton

class Redgay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def get_client(self):
        return self.bot

    @app_commands.command(name="隨機圖", description="可以隨機給你一張圖片")
    async def img(self, interaction: discord.Interaction):
        await interaction.response.defer()
        start_time = datetime.datetime.now()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.redbean0721.com/api/img?type=json") as api_response:
                end_time = datetime.datetime.now()
                if api_response.status != 200:
                    await interaction.followup.send("無法獲取圖片，請稍後再試。")
                    return
                data = await api_response.json()
                image_url = data.get("url")
                tag = data.get("tag")
                color_task = asyncio.create_task(get_dominant_color(image_url))
                image_task = asyncio.create_task(session.get(image_url))
                image_response = await image_task
                image_bytes = await image_response.read()
                embed_color = await color_task
                elapsed = (end_time - start_time).total_seconds()
                embed = discord.Embed(
                    title="隨機圖",
                    color=embed_color,
                    description=f"提示詞: {tag}",
                )
                file = discord.File(BytesIO(image_bytes), filename="image.jpg")
                embed.set_image(url="attachment://image.jpg")
                embed.set_footer(text=f"回應時間: {elapsed:.2f}s")
                embed.timestamp = datetime.datetime.now()
                view = RefreshButton(image_url=image_url)
                await interaction.followup.send(embed=embed, view=view, file=file)


async def setup(bot):
    await bot.add_cog(Redgay(bot))