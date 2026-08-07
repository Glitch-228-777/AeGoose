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


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
