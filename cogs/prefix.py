import discord
from discord.ext import commands
import logging


class _PrefixResponse:
    def __init__(self, owner: "PrefixInteraction"):
        self._owner = owner
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, *args, **kwargs):
        self._done = True

    async def send_message(self, content=None, **kwargs):
        self._done = True
        return await self._owner._send(content, **kwargs)

    async def edit_message(self, **kwargs):
        self._done = True
        return await self._owner.edit_original_response(**kwargs)


class _PrefixFollowup:
    def __init__(self, owner: "PrefixInteraction"):
        self._owner = owner

    async def send(self, content=None, **kwargs):
        return await self._owner._send(content, **kwargs)


class PrefixInteraction:
    def __init__(self, ctx: commands.Context):
        self._ctx = ctx
        self._original: discord.Message | None = None
        self.user = ctx.author
        self.guild = ctx.guild
        self.guild_id = ctx.guild.id if ctx.guild else None
        self.channel = ctx.channel
        self.channel_id = ctx.channel.id
        self.client = ctx.bot
        self.message = ctx.message
        self.response = _PrefixResponse(self)
        self.followup = _PrefixFollowup(self)

    async def _send(self, content=None, **kwargs):
        kwargs.pop("ephemeral", None)
        kwargs.pop("wait", None)
        message = await self._ctx.send(content, **kwargs)
        if self._original is None:
            self._original = message
        return message

    async def edit_original_response(self, **kwargs):
        if self._original is None:
            return await self._send(**kwargs)
        kwargs.pop("ephemeral", None)
        return await self._original.edit(**kwargs)

    async def original_response(self):
        return self._original


class PrefixCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    async def _run(self, ctx: commands.Context, cog_name: str, command_name: str, *args):
        cog = self.bot.get_cog(cog_name)
        command = getattr(cog, command_name, None) if cog else None
        if command is None:
            await ctx.send(f"❌ 找不到指令模組 `{cog_name}`，可能尚未載入")
            return
        await command.callback(cog, PrefixInteraction(ctx), *args)

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        await self._run(ctx, "Musicplay", "play", query)

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        await self._run(ctx, "Musicplay", "pause")

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx: commands.Context):
        await self._run(ctx, "Musicplay", "resume")

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx: commands.Context):
        await self._run(ctx, "Musicplay", "skip")

    @commands.command(name="volume", aliases=["vol", "v"])
    async def volume(self, ctx: commands.Context, vol: int):
        await self._run(ctx, "Musicplay", "volume", vol)

    @commands.command(name="controller", aliases=["np", "c"])
    async def controller(self, ctx: commands.Context):
        await self._run(ctx, "Musicplay", "musiccontrol")

    @commands.command(name="loop", aliases=["l"])
    async def loop(self, ctx: commands.Context):
        await self._run(ctx, "Musicplay", "loop")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        await self._run(ctx, "Queue", "queue")

    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context):
        await self._run(ctx, "Queue", "clear")

    @commands.command(name="remove", aliases=["rm"])
    async def remove(self, ctx: commands.Context, position: int):
        await self._run(ctx, "Queue", "remove", position)

    @commands.command(name="shuffle", aliases=["sh"])
    async def shuffle(self, ctx: commands.Context):
        await self._run(ctx, "Queue", "shuffle")

    @commands.command(name="insert", aliases=["i", "pn"])
    async def insert(self, ctx: commands.Context, *, query: str):
        await self._run(ctx, "Queue", "insert", query)

    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        await self._run(ctx, "Other", "stop")

    @commands.command(name="leave", aliases=["dc"])
    async def leave(self, ctx: commands.Context):
        await self._run(ctx, "botcommand", "leave")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await self._run(ctx, "Other", "ping")

    @commands.command(name="help", aliases=["h"])
    async def help(self, ctx: commands.Context):
        lines = [
            "`p!play <歌名/連結>` (`p!p`) 播放",
            "`p!pause` 暫停　`p!resume` (`p!r`) 繼續",
            "`p!skip` (`p!s`) 跳過　`p!stop` 停止並清空",
            "`p!volume <0-150>` (`p!vol`) 音量",
            "`p!loop` (`p!l`) 循環　`p!controller` (`p!np`) 控制器",
            "`p!queue` (`p!q`) 播放清單　`p!shuffle` 隨機　`p!clear` 清空",
            "`p!remove <位置>` (`p!rm`) 移除　`p!insert <歌名/連結>` (`p!i`) 插播",
            "`p!leave` (`p!dc`) 離開語音　`p!ping` 延遲",
        ]
        embed = discord.Embed(title="📚 p! 指令", description="\n".join(lines), color=discord.Color.green())
        embed.set_footer(text="也可以使用 /help 查看 slash 指令")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ 這個指令只能在伺服器中使用")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ 缺少參數 `{error.param.name}`，用 `p!help` 查看用法")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ 參數格式錯誤，用 `p!help` 查看用法")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("❌ 你沒有權限使用此指令")
        else:
            original = getattr(error, "original", error)
            logging.error(f"p! 指令執行錯誤：{original!r}", exc_info=original)
            await ctx.send(f"❌ 指令執行時發生錯誤：{original}")


async def setup(bot: commands.Bot):
    await bot.add_cog(PrefixCommands(bot))
