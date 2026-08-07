import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
import storage
from utils import is_admin, deny, log_action, mod_embed, now_utc


class AntiSpam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_tracker: dict[int, dict[int, deque]] = defaultdict(lambda: defaultdict(deque))
        self.ping_tracker: dict[int, dict[int, dict[int, deque]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(deque)))

    async def _punish_spammer(self, message: discord.Message, cfg: dict):
        if cfg.get("antispam_action") != "timeout":
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return
        if member.guild_permissions.administrator:
            return
        try:
            await member.timeout(timedelta(minutes=cfg.get("antispam_timeout_minutes", 10)), reason="Авто-антиспам")
            await log_action(message.guild, mod_embed(
                "Авто-таймаут (спам)", message.guild.me, member,
                f"Превышен лимит в {message.channel.mention}", config.COLOR_WARN))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        user_id = message.author.id
        channel_id = message.channel.id

        ebalooff = storage.get_ebalooff()
        if str(user_id) in ebalooff:
            try:
                until = datetime.fromisoformat(ebalooff[str(user_id)])
            except ValueError:
                until = None
            if until and now_utc() < until:
                await asyncio.sleep(1)
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
                return
            else:
                storage.remove_ebalooff(user_id)

        cfg = storage.get_config(message.guild.id)
        if cfg.get("antispam_enabled", True) and not message.author.guild_permissions.administrator:
            message_limit = cfg.get("message_limit", 8)
            ping_limit = cfg.get("ping_limit", 6)

            msg_queue = self.message_tracker[channel_id][user_id]
            msg_queue.append(message)
            if len(msg_queue) >= message_limit:
                to_delete = list(msg_queue)[:-1]
                msg_queue.clear()
                msg_queue.append(message)
                try:
                    await message.channel.delete_messages(to_delete)
                except (discord.NotFound, discord.HTTPException):
                    pass
                await self._punish_spammer(message, cfg)

            if message.mentions:
                for mentioned in message.mentions:
                    if mentioned.bot:
                        continue
                    ping_queue = self.ping_tracker[channel_id][user_id][mentioned.id]
                    ping_queue.append(message)
                    if len(ping_queue) >= ping_limit:
                        to_delete = [m for m in list(ping_queue)[:-1] if m.id != message.id]
                        ping_queue.clear()
                        ping_queue.append(message)
                        to_delete_unique = list({m.id: m for m in to_delete}.values())
                        if to_delete_unique:
                            try:
                                await message.channel.delete_messages(to_delete_unique)
                            except (discord.NotFound, discord.HTTPException):
                                pass
                        await self._punish_spammer(message, cfg)

    @app_commands.command(name="antispam", description="Включить или выключить защиту от спама")
    @app_commands.describe(state="Включить или выключить")
    @app_commands.choices(state=[
        app_commands.Choice(name="включить", value="on"),
        app_commands.Choice(name="выключить", value="off"),
    ])
    async def antispam(self, interaction: discord.Interaction, state: app_commands.Choice[str]):
        if not is_admin(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)
        enabled = state.value == "on"
        storage.set_config(interaction.guild.id, antispam_enabled=enabled)
        await interaction.response.send_message(f"Анти-спам {'включён' if enabled else 'выключен'}.", ephemeral=True)

    @app_commands.command(name="antispamconfig", description="Настроить параметры защиты от спама")
    @app_commands.describe(message_limit="Сколько сообщений подряд считать спамом", ping_limit="Сколько пингов считать спамом",
                            action="Что делать со спамером", timeout_minutes="На сколько минут выдавать таймаут")
    @app_commands.choices(action=[
        app_commands.Choice(name="только удалять", value="delete"),
        app_commands.Choice(name="удалять и выдавать таймаут", value="timeout"),
    ])
    async def antispamconfig(self, interaction: discord.Interaction, message_limit: int = None, ping_limit: int = None,
                              action: app_commands.Choice[str] = None, timeout_minutes: int = None):
        if not is_admin(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)
        updates = {}
        if message_limit is not None:
            updates["message_limit"] = max(3, message_limit)
        if ping_limit is not None:
            updates["ping_limit"] = max(2, ping_limit)
        if action is not None:
            updates["antispam_action"] = action.value
        if timeout_minutes is not None:
            updates["antispam_timeout_minutes"] = max(1, timeout_minutes)
        if updates:
            storage.set_config(interaction.guild.id, **updates)
        cfg = storage.get_config(interaction.guild.id)
        await interaction.response.send_message(
            f"Настройки анти-спама:\n"
            f"Лимит сообщений: {cfg['message_limit']}\n"
            f"Лимит пингов: {cfg['ping_limit']}\n"
            f"Действие: {cfg['antispam_action']}\n"
            f"Таймаут: {cfg['antispam_timeout_minutes']}м",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiSpam(bot))
