import discord
from discord import app_commands
from discord.ext import commands

import config
import storage
from utils import is_admin, deny


class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setlogchannel", description="Выбрать канал, куда писать логи модерации")
    @app_commands.describe(channel="Канал для логов (оставь пустым, чтобы отключить)")
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        if not is_admin(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)
        storage.set_config(interaction.guild.id, log_channel=channel.id if channel else None)
        if channel:
            await interaction.response.send_message(f"Логи модерации будут в {channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message("Логи модерации отключены.", ephemeral=True)

    @app_commands.command(name="sync", description="Принудительно синхронизировать slash-команды бота")
    async def sync_commands(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)
        await interaction.response.defer(ephemeral=True)
        try:
            if config.GUILD_ID and config.GUILD_ID.isdigit():
                guild_object = discord.Object(id=int(config.GUILD_ID))
                self.bot.tree.copy_global_to(guild=guild_object)
                synced = await self.bot.tree.sync(guild=guild_object)
            else:
                synced = await self.bot.tree.sync()
            await interaction.followup.send(f"Успешно синхронизировано {len(synced)} команд!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Ошибка синхронизации: `{e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
