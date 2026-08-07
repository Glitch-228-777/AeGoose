import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
import storage
from utils import now_utc, has_report_role, deny, log_action, mod_embed


class WarningView(discord.ui.LayoutView):
    def __init__(self, member: discord.Member, moderator, reason: str, unix_ts: int):
        super().__init__(timeout=None)
        container = discord.ui.Container()

        container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(config.WARNING_BANNER_URL)))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))

        container.add_item(discord.ui.Section(
            f"**Модератор:**\n{moderator.mention}\n\n",
            accessory=discord.ui.Thumbnail(moderator.display_avatar.url),
        ))
        container.add_item(discord.ui.Section(
            f"**Цель:**\n{member.mention}",
            accessory=discord.ui.Thumbnail(member.display_avatar.url),
        ))

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"**Причина:**\n{reason}"))
        container.add_item(discord.ui.Separator(visible=False))
        container.add_item(discord.ui.TextDisplay(f"<t:{unix_ts}:f>"))

        self.add_item(container)


class ReportModal(discord.ui.Modal, title="Форма Жалобы"):
    reason = discord.ui.TextInput(label="Причина репорта", placeholder="Опишите причину жалобы подробно...",
                                   style=discord.TextStyle.paragraph, required=True, max_length=1000)
    evidence = discord.ui.TextInput(label="Доказательства", placeholder="Ссылки на скриншоты или видео...",
                                     style=discord.TextStyle.paragraph, required=True, max_length=1000)
    extra = discord.ui.TextInput(label="Дополнительная информация", placeholder="Необязательно...",
                                  style=discord.TextStyle.paragraph, required=False, max_length=1000)

    def __init__(self, accused_member: discord.Member):
        super().__init__()
        self.accused_member = accused_member

    async def on_submit(self, interaction: discord.Interaction):
        number = storage.next_appeal_number()
        guild = interaction.guild
        report_role = guild.get_role(config.REPORT_ROLE_ID)

        thread = await interaction.channel.create_thread(
            name=f"жалоба-{number}",
            type=discord.ChannelType.private_thread,
            invitable=False
        )

        if report_role:
            for m in guild.members:
                if report_role in m.roles and not m.bot:
                    try:
                        await thread.add_member(m)
                    except Exception:
                        pass
        try:
            await thread.add_member(interaction.user)
        except Exception:
            pass

        embed = discord.Embed(title=f"Жалоба #{number}", color=config.COLOR_ERR, timestamp=now_utc())
        embed.set_thumbnail(url=self.accused_member.display_avatar.url)
        embed.add_field(name="Податель жалобы", value=f"{interaction.user.mention}\n`{interaction.user}`", inline=True)
        embed.add_field(name="Обвиняемый", value=f"{self.accused_member.mention}\n`{self.accused_member}`", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(name="Причина репорта", value=f"```{self.reason.value}```", inline=False)
        embed.add_field(name="Доказательства", value=f"```{self.evidence.value}```", inline=False)
        if self.extra.value:
            embed.add_field(name="Дополнительная информация", value=f"```{self.extra.value}```", inline=False)
        embed.set_footer(text="Используйте /closeappeal для закрытия жалобы")

        ping_content = (report_role.mention if report_role else "") + f" {interaction.user.mention}"
        await thread.send(content=ping_content.strip(), embed=embed)
        await interaction.response.send_message(f"Жалоба **#{number}** подана! Перейди в ветку: {thread.mention}", ephemeral=True)


class UserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Выберите участника сервера...", min_values=1, max_values=1)
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        accused = select.values[0]
        if accused.id == interaction.user.id:
            return await interaction.response.send_message("Нельзя подать жалобу на самого себя.", ephemeral=True)
        if accused.bot:
            return await interaction.response.send_message("Нельзя подать жалобу на бота.", ephemeral=True)
        await interaction.response.send_modal(ReportModal(accused_member=accused))


class ReportButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать жалобу", style=discord.ButtonStyle.danger, custom_id="report_button")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Выбор участника", description="Выберите участника сервера, на которого хотите подать жалобу.",
                               color=config.COLOR_ERR)
        await interaction.response.send_message(embed=embed, view=UserSelectView(), ephemeral=True)


class Reports(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reportmsg", description="Опубликовать сообщение с кнопкой для подачи жалоб")
    async def reportmsg(self, interaction: discord.Interaction):
        if not has_report_role(interaction):
            return await deny(interaction, "У тебя нет прав для использования этой команды.")
        embed = discord.Embed(
            title="Подача жалобы",
            description=(
                "Если у вас есть жалоба на участника сервера - нажмите кнопку ниже.\n\n"
                "**Что потребуется:**\n"
                "> Участник которого хотите репорнуть\n"
                "> Причина жалобы\n"
                "> Доказательства (скриншоты / видео)\n\n"
                "После отправки будет создана приватная ветка,\nдоступная только вам и модераторам."
            ),
            color=config.COLOR_ERR
        )
        embed.set_footer(text="Подавайте жалобы только по делу")
        await interaction.response.send_message(embed=embed, view=ReportButtonView())

    @app_commands.command(name="closeappeal", description="Закрыть текущую жалобу и удалить ветку")
    @app_commands.describe(reason="Почему закрываем жалобу")
    async def closeappeal(self, interaction: discord.Interaction, reason: str = "Причина не указана"):
        if not has_report_role(interaction):
            return await deny(interaction, "У тебя нет прав для использования этой команды.")
        channel = interaction.channel
        if not isinstance(channel, discord.Thread):
            return await deny(interaction, "Эта команда работает только внутри ветки жалобы.")
        embed = discord.Embed(
            title="Жалоба закрыта",
            description=f"**Причина:** {reason}\n\nВетка будет удалена через 5 секунд.",
            color=config.COLOR_NEUTRAL, timestamp=now_utc())
        embed.set_footer(text=f"Закрыл: {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await log_action(interaction.guild, mod_embed(
            "Жалоба закрыта", interaction.user, None, f"{channel.name}: {reason}", config.COLOR_NEUTRAL))
        await asyncio.sleep(5)
        await channel.delete()


async def setup(bot: commands.Bot):
    await bot.add_cog(Reports(bot))
