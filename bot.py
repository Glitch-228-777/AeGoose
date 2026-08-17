import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
from keep_alive import keep_alive
from cogs import EXTENSIONS
from cogs.reports import ReportButtonView
from utils import deny


class AdminBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        self.add_view(ReportButtonView())

    async def on_ready(self):
        if config.GUILD_ID and config.GUILD_ID.isdigit():
            guild_object = discord.Object(id=int(config.GUILD_ID))
            self.tree.copy_global_to(guild=guild_object)
            await self.tree.sync(guild=guild_object)
        else:
            await self.tree.sync()
        print(f"{self.user} запущен")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        raise error


def create_bot() -> AdminBot:
    new_bot = AdminBot()

    @new_bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Подожди {error.retry_after:.1f}с перед повторным использованием."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "У тебя недостаточно прав для этой команды."
        else:
            msg = f"Произошла ошибка при выполнении команды: `{type(error).__name__}`"
            print(f"[APP COMMAND ERROR] {error!r}")
        try:
            await deny(interaction, msg)
        except discord.HTTPException:
            pass

    return new_bot


async def run_with_backoff():
    delay = 30
    max_delay = 900
    while True:
        bot = create_bot()
        try:
            async with bot:
                await bot.start(config.TOKEN)
            return
        except discord.HTTPException as error:
            if error.status == 429:
                print(f"Discord вернул 429, жду {delay}с перед повторной попыткой логина")
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
                continue
            raise
        except discord.LoginFailure:
            print("Неверный токен, останавливаюсь")
            return


if __name__ == "__main__":
    keep_alive()
    asyncio.run(run_with_backoff())
