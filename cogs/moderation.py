import asyncio
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
import storage
from utils import now_utc, has_allowed_role, deny, can_moderate, log_action, mod_embed
from cogs.reports import WarningView


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ban", description="Забанить участника на сервере")
    @app_commands.describe(member="Кого баним", reason="За что бан", delete_days="За сколько дней удалить его сообщения (0-7)")
    async def ban(self, interaction: discord.Interaction, member: discord.Member,
                  reason: str = "Причина не указана", delete_days: int = 0):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        delete_days = max(0, min(7, delete_days))
        try:
            await member.ban(reason=f"{interaction.user}: {reason}", delete_message_days=delete_days)
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для бана этого участника.")
        await interaction.response.send_message(f"{member.mention} забанен. Причина: {reason}", ephemeral=True)
        await log_action(interaction.guild, mod_embed("Участник забанен", interaction.user, member, reason, config.COLOR_ERR))

    @app_commands.command(name="unban", description="Снять бан с пользователя по его ID")
    @app_commands.describe(user_id="ID пользователя, которого нужно разбанить", reason="Почему снимаем бан")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        if not user_id.isdigit():
            return await deny(interaction, "Укажи корректный ID.")
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"{interaction.user}: {reason}")
        except discord.NotFound:
            return await deny(interaction, "Пользователь не найден в бан-листе.")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для разбана.")
        await interaction.response.send_message(f"{user} разбанен.", ephemeral=True)
        await log_action(interaction.guild, mod_embed("Пользователь разбанен", interaction.user, user, reason, config.COLOR_OK))

    @app_commands.command(name="kick", description="Выгнать участника с сервера")
    @app_commands.describe(member="Кого выгнать", reason="За что")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        try:
            await member.kick(reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для кика этого участника.")
        await interaction.response.send_message(f"{member} выгнан. Причина: {reason}", ephemeral=True)
        await log_action(interaction.guild, mod_embed("Участник выгнан", interaction.user, member, reason, config.COLOR_WARN))

    @app_commands.command(name="timeout", description="Выдать участнику временный мут (таймаут)")
    @app_commands.describe(member="Кого мутим", minutes="На сколько минут", hours="На сколько часов",
                            days="На сколько дней", reason="За что")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member,
                       minutes: int = 0, hours: int = 0, days: int = 0, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        duration = timedelta(days=days, hours=hours, minutes=minutes)
        if duration.total_seconds() <= 0:
            return await deny(interaction, "Укажи длительность таймаута.")
        if duration > config.MAX_TIMEOUT:
            duration = config.MAX_TIMEOUT
        try:
            await member.timeout(duration, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для таймаута этого участника.")
        await interaction.response.send_message(
            f"{member.mention} в таймауте на {days}д {hours}ч {minutes}м. Причина: {reason}", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Таймаут", interaction.user, member, reason, config.COLOR_WARN,
            extra={"Длительность": f"{days}д {hours}ч {minutes}м"}))

    @app_commands.command(name="untimeout", description="Снять мут с участника")
    @app_commands.describe(member="С кого снять мут", reason="Почему")
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        try:
            await member.timeout(None, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для снятия таймаута.")
        await interaction.response.send_message(f"С {member.mention} снят таймаут.", ephemeral=True)
        await log_action(interaction.guild, mod_embed("Таймаут снят", interaction.user, member, reason, config.COLOR_OK))

    @app_commands.command(name="mute", description="Замутить участника в голосовом чате (до 10 минут)")
    @app_commands.describe(member="Кого замутить в войсе", minutes="На сколько минут (максимум 10)", reason="За что")
    async def mute(self, interaction: discord.Interaction, member: discord.Member,
                    minutes: int = 5, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        if member.voice is None or member.voice.channel is None:
            return await deny(interaction, "Участник сейчас не в голосовом канале.")
        minutes = max(1, min(10, minutes))
        try:
            await member.edit(mute=True, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для мута этого участника в голосовом чате.")
        await interaction.response.send_message(
            f"{member.mention} замучен в голосовом чате на {minutes}м. Причина: {reason}", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Мут в голосовом чате", interaction.user, member, reason, config.COLOR_WARN,
            extra={"Длительность": f"{minutes}м"}))
        asyncio.create_task(self._auto_unmute(interaction.guild.id, member.id, minutes * 60))

    async def _auto_unmute(self, guild_id: int, member_id: int, delay: int):
        await asyncio.sleep(delay)
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        target = guild.get_member(member_id)
        if target is None or not target.voice or not target.voice.mute:
            return
        try:
            await target.edit(mute=False, reason="Автоматическое снятие мута")
            await log_action(guild, mod_embed("Мут в голосовом чате снят", guild.me, target, "Истекло время", config.COLOR_OK))
        except discord.HTTPException:
            pass

    @app_commands.command(name="unmute", description="Снять голосовой мут с участника")
    @app_commands.describe(member="С кого снять голосовой мут", reason="Почему")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        try:
            await member.edit(mute=False, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав для снятия голосового мута.")
        await interaction.response.send_message(f"С {member.mention} снят голосовой мут.", ephemeral=True)
        await log_action(interaction.guild, mod_embed("Голосовой мут снят", interaction.user, member, reason, config.COLOR_OK))

    @app_commands.command(name="chatmute", description="Запретить участнику писать в конкретном текстовом канале")
    @app_commands.describe(member="Кого мутим", channel="В каком канале запретить писать",
                            minutes="На сколько минут (пусто = до ручного размута)", reason="За что")
    async def chatmute(self, interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel,
                        minutes: int | None = None, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        try:
            await channel.set_permissions(
                member, send_messages=False, add_reactions=False, send_messages_in_threads=False,
                create_public_threads=False, create_private_threads=False, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав менять доступ в этом канале.")

        if minutes is not None:
            minutes = max(1, minutes)
            await interaction.response.send_message(
                f"{member.mention} не может писать в {channel.mention} {minutes}м. Причина: {reason}", ephemeral=True)
            await log_action(interaction.guild, mod_embed(
                "Мут в чате", interaction.user, member, reason, config.COLOR_WARN,
                extra={"Канал": channel.mention, "Длительность": f"{minutes}м"}))
            asyncio.create_task(self._auto_chatunmute(interaction.guild.id, channel.id, member.id, minutes * 60))
        else:
            await interaction.response.send_message(
                f"{member.mention} не может писать в {channel.mention} (до ручного размута). Причина: {reason}", ephemeral=True)
            await log_action(interaction.guild, mod_embed(
                "Мут в чате", interaction.user, member, reason, config.COLOR_WARN,
                extra={"Канал": channel.mention, "Длительность": "До ручного снятия"}))

    async def _auto_chatunmute(self, guild_id: int, channel_id: int, member_id: int, delay: int):
        await asyncio.sleep(delay)
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        ch = guild.get_channel(channel_id)
        target = guild.get_member(member_id)
        if ch is None or target is None:
            return
        try:
            await ch.set_permissions(target, overwrite=None, reason="Автоматическое снятие мута в чате")
            await log_action(guild, mod_embed(
                "Мут в чате снят", guild.me, target, "Истекло время", config.COLOR_OK, extra={"Канал": ch.mention}))
        except discord.HTTPException:
            pass

    @app_commands.command(name="chatunmute", description="Снять запрет на письмо в текстовом канале")
    @app_commands.describe(member="С кого снять мут", channel="В каком канале вернуть доступ", reason="Почему")
    async def chatunmute(self, interaction: discord.Interaction, member: discord.Member,
                          channel: discord.TextChannel, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        try:
            await channel.set_permissions(member, overwrite=None, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав менять доступ в этом канале.")
        await interaction.response.send_message(f"{member.mention} снова может писать в {channel.mention}.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Мут в чате снят", interaction.user, member, reason, config.COLOR_OK, extra={"Канал": channel.mention}))

    @app_commands.command(name="voiceban", description="Запретить участнику заходить в голосовой канал")
    @app_commands.describe(member="Кому запрещаем", channel="В какой войс запретить вход",
                            minutes="На сколько минут", reason="За что")
    async def voiceban(self, interaction: discord.Interaction, member: discord.Member,
                        channel: discord.VoiceChannel | None = None, minutes: int | None = None,
                        reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        targets = [channel] if channel is not None else list(interaction.guild.voice_channels)
        if not targets:
            return await deny(interaction, "На сервере нет голосовых каналов.")
        try:
            for vc in targets:
                await vc.set_permissions(member, connect=False, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав менять доступ в голосовых каналах.")
        if member.voice and member.voice.channel and (channel is None or member.voice.channel.id == channel.id):
            try:
                await member.move_to(None)
            except discord.HTTPException:
                pass
        scope = channel.mention if channel is not None else "все голосовые каналы"
        duration = f"{max(1, minutes)}м" if minutes is not None else "До ручного снятия"
        await interaction.response.send_message(f"{member.mention} не может заходить в {scope}. Причина: {reason}", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Запрет входа в войс", interaction.user, member, reason, config.COLOR_WARN,
            extra={"Канал": scope, "Длительность": duration}))
        if minutes is not None:
            channel_id = channel.id if channel is not None else None
            asyncio.create_task(self._auto_voiceunban(interaction.guild.id, channel_id, member.id, max(1, minutes) * 60, scope))

    async def _auto_voiceunban(self, guild_id: int, channel_id, member_id: int, delay: int, scope: str):
        await asyncio.sleep(delay)
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        target = guild.get_member(member_id)
        if target is None:
            return
        vcs = [guild.get_channel(channel_id)] if channel_id is not None else list(guild.voice_channels)
        for vc in vcs:
            if vc is None:
                continue
            try:
                await vc.set_permissions(target, overwrite=None, reason="Автоматическое снятие запрета входа")
            except discord.HTTPException:
                pass
        await log_action(guild, mod_embed(
            "Запрет входа в войс снят", guild.me, target, "Истекло время", config.COLOR_OK, extra={"Канал": scope}))

    @app_commands.command(name="voiceunban", description="Снять запрет на вход в голосовой канал")
    @app_commands.describe(member="С кого снять запрет", channel="С какого войса снять (пусто = со всех)", reason="Почему")
    async def voiceunban(self, interaction: discord.Interaction, member: discord.Member,
                          channel: discord.VoiceChannel | None = None, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        targets = [channel] if channel is not None else list(interaction.guild.voice_channels)
        try:
            for vc in targets:
                await vc.set_permissions(member, overwrite=None, reason=f"{interaction.user}: {reason}")
        except discord.Forbidden:
            return await deny(interaction, "Нет прав менять доступ в голосовых каналах.")
        scope = channel.mention if channel is not None else "все голосовые каналы"
        await interaction.response.send_message(f"{member.mention} снова может заходить в {scope}.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Запрет входа в войс снят", interaction.user, member, reason, config.COLOR_OK, extra={"Канал": scope}))

    @app_commands.command(name="warn", description="Выдать участнику предупреждение")
    @app_commands.describe(member="Кому выдаём предупреждение", reason="За что")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        ok, why = can_moderate(interaction, member)
        if not ok:
            return await deny(interaction, why)
        entry = {
            "reason": reason,
            "mod": str(interaction.user),
            "mod_id": interaction.user.id,
            "ts": now_utc().isoformat(),
        }
        total = storage.add_warning(interaction.guild.id, member.id, entry)
        unix_ts = int(now_utc().timestamp())
        await interaction.response.send_message(view=WarningView(member, interaction.user, reason, unix_ts))
        await log_action(interaction.guild, mod_embed(
            "Предупреждение", interaction.user, member, reason, config.COLOR_WARN,
            extra={"Всего предупреждений": str(total)}))

    @app_commands.command(name="warnings", description="Посмотреть предупреждения участника")
    @app_commands.describe(member="Чьи предупреждения показать")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        items = storage.get_warnings(interaction.guild.id, member.id)
        if not items:
            return await interaction.response.send_message(f"У {member.mention} нет предупреждений.", ephemeral=True)
        embed = discord.Embed(title=f"Предупреждения - {member}", color=config.COLOR_WARN)
        for i, w in enumerate(items[-25:], 1):
            ts = w.get("ts", "")[:10]
            embed.add_field(name=f"#{i} • {ts} • {w.get('mod', '')}", value=w.get("reason", ""), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarns", description="Убрать все предупреждения у участника")
    @app_commands.describe(member="У кого очистить предупреждения")
    async def clearwarns(self, interaction: discord.Interaction, member: discord.Member):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        count = storage.clear_warnings(interaction.guild.id, member.id)
        await interaction.response.send_message(f"У {member.mention} удалено предупреждений: {count}.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Предупреждения очищены", interaction.user, member, f"Удалено: {count}", config.COLOR_OK))

    @app_commands.command(name="slowmode", description="Включить медленный режим в этом канале")
    @app_commands.describe(seconds="Задержка между сообщениями в секундах (0 - выключить)")
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        seconds = max(0, min(21600, seconds))
        await interaction.channel.edit(slowmode_delay=seconds)
        await interaction.response.send_message(f"Медленный режим: {seconds}с.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Медленный режим", interaction.user, None, f"{seconds}с в {interaction.channel.mention}", config.COLOR_INFO))

    @app_commands.command(name="lock", description="Закрыть канал")
    @app_commands.describe(reason="Причина")
    async def lock(self, interaction: discord.Interaction, reason: str = "Причина не указана"):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        everyone = interaction.guild.default_role
        overwrite = interaction.channel.overwrites_for(everyone)
        overwrite.send_messages = False
        await interaction.channel.set_permissions(everyone, overwrite=overwrite, reason=reason)
        await interaction.response.send_message("Канал закрыт.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Канал закрыт", interaction.user, None, f"{interaction.channel.mention}: {reason}", config.COLOR_WARN))

    @app_commands.command(name="unlock", description="Снова открыть канал для сообщений")
    async def unlock(self, interaction: discord.Interaction):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        everyone = interaction.guild.default_role
        overwrite = interaction.channel.overwrites_for(everyone)
        overwrite.send_messages = None
        await interaction.channel.set_permissions(everyone, overwrite=overwrite)
        await interaction.response.send_message("Канал открыт.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Канал открыт", interaction.user, None, interaction.channel.mention, config.COLOR_OK))

    @app_commands.command(name="clear", description="Удалить сообщения в этом чате")
    @app_commands.describe(member="Удалить только сообщения этого участника", amount="Сколько сообщений удалить")
    async def clear(self, interaction: discord.Interaction, member: discord.Member = None, amount: int = None):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)

        await interaction.response.defer(ephemeral=True)

        def check(m):
            return member is None or m.author.id == member.id

        try:
            limit = amount if amount is not None else 1000
            deleted = await interaction.channel.purge(limit=limit, check=check)
        except discord.Forbidden:
            return await interaction.followup.send("Нет прав на удаление сообщений.", ephemeral=True)

        await interaction.followup.send(f"Удалено сообщений: {len(deleted)}.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Очистка чата", interaction.user, member,
            f"Удалено {len(deleted)} в {interaction.channel.mention}", config.COLOR_INFO))

    @app_commands.command(name="ebalooff", description="Автоматически удалять сообщения участника в течение времени")
    @app_commands.describe(member="У кого удалять сообщения", hours="Сколько часов", minutes="Сколько минут", seconds="Сколько секунд")
    async def ebalooff(self, interaction: discord.Interaction, member: discord.Member,
                        hours: int = 0, minutes: int = 0, seconds: int = 0):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        if total_seconds <= 0:
            return await deny(interaction, "Укажи время.")
        until = now_utc() + timedelta(seconds=total_seconds)
        storage.set_ebalooff(member.id, until.isoformat())
        await interaction.response.send_message(
            f"Сообщения {member.mention} будут удаляться {hours}ч {minutes}м {seconds}с.", ephemeral=True)
        await log_action(interaction.guild, mod_embed(
            "Ebalooff", interaction.user, member, f"{hours}ч {minutes}м {seconds}с", config.COLOR_WARN))

    @app_commands.command(name="ebaloon", description="Отменить автоудаление сообщений участника")
    @app_commands.describe(member="Кого размутить")
    async def ebaloon(self, interaction: discord.Interaction, member: discord.Member):
        if not has_allowed_role(interaction):
            return await deny(interaction, config.NO_PERMISSION_MSG)
        if storage.remove_ebalooff(member.id):
            await interaction.response.send_message(f"{member.mention} размучен.", ephemeral=True)
            await log_action(interaction.guild, mod_embed("Ebalooff снят", interaction.user, member, None, config.COLOR_OK))
        else:
            await interaction.response.send_message(f"{member.mention} не был замучен.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
