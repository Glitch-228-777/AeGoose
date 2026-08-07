import discord
from discord import app_commands
from discord.ext import commands

import config
import storage
from utils import now_utc


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="userinfo", description="Показать информацию об участнике")
    @app_commands.describe(member="О ком показать информацию (по умолчанию - о себе)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        warns = len(storage.get_warnings(interaction.guild.id, member.id))
        embed = discord.Embed(title=f"Инфо: {member}", color=member.color if member.color.value else config.COLOR_INFO)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Предупреждения", value=str(warns), inline=True)
        embed.add_field(name="Старшая роль", value=member.top_role.mention, inline=True)
        if member.joined_at:
            embed.add_field(name="На сервере с", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
        embed.add_field(name="Аккаунт создан", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        if member.is_timed_out():
            embed.add_field(name="Таймаут до", value=discord.utils.format_dt(member.timed_out_until, "R"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Показать информацию о сервере")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(title=g.name, color=config.COLOR_INFO, timestamp=now_utc())
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="Участников", value=str(g.member_count), inline=True)
        embed.add_field(name="Каналов", value=str(len(g.channels)), inline=True)
        embed.add_field(name="Ролей", value=str(len(g.roles)), inline=True)
        embed.add_field(name="Создан", value=discord.utils.format_dt(g.created_at, "R"), inline=True)
        if g.owner:
            embed.add_field(name="Владелец", value=g.owner.mention, inline=True)
        embed.add_field(name="Бустов", value=str(g.premium_subscription_count), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Проверить пинг бота")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Понг! Задержка {round(self.bot.latency * 1000)}мс", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
