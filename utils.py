from datetime import datetime, timezone

import discord

import config
import storage


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def has_allowed_role(interaction: discord.Interaction) -> bool:
    user_role_ids = {role.id for role in interaction.user.roles}
    return bool(user_role_ids.intersection(config.ALLOWED_ROLE_IDS)) or interaction.user.guild_permissions.administrator


def has_report_role(interaction: discord.Interaction) -> bool:
    return any(r.id == config.REPORT_ROLE_ID for r in interaction.user.roles) or interaction.user.guild_permissions.administrator


def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


async def deny(interaction: discord.Interaction, msg: str):
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


def can_moderate(interaction: discord.Interaction, member: discord.Member) -> tuple[bool, str]:
    if member.id == interaction.user.id:
        return False, "Нельзя применить эту команду к самому себе."
    if member.bot:
        return False, "Нельзя применить эту команду к боту."
    if member.id == interaction.guild.owner_id:
        return False, "Нельзя модерировать владельца сервера."
    author = interaction.user
    if isinstance(author, discord.Member) and author.id != interaction.guild.owner_id:
        if member.top_role >= author.top_role:
            return False, "У цели роль выше или равна твоей."
    me = interaction.guild.me
    if member.top_role >= me.top_role:
        return False, "У цели роль выше моей."
    return True, ""


async def log_action(guild: discord.Guild, embed: discord.Embed):
    if guild is None:
        return
    cfg = storage.get_config(guild.id)
    channel_id = cfg.get("log_channel")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        return
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        pass


def mod_embed(title, moderator, target, reason=None, color=config.COLOR_NEUTRAL, extra=None):
    embed = discord.Embed(title=title, color=color, timestamp=now_utc())
    embed.add_field(name="Модератор", value=f"{moderator.mention}\n`{moderator}`", inline=True)
    if target is not None:
        embed.add_field(name="Цель", value=f"{getattr(target, 'mention', target)}\n`{target}`", inline=True)
    if reason:
        embed.add_field(name="Причина", value=reason, inline=False)
    if extra:
        for name, value in extra.items():
            embed.add_field(name=name, value=value, inline=False)
    return embed
