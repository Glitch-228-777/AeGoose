import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import aiohttp
import json
import re

import config
import storage
from utils import has_full_access, deny

WEBHOOK_URL = "https://discord.com/api/webhooks/1539728892246360064/1ci4aRaaLIrXteIhJ5Gxi_aWedxbL7s5aZK8vSqRseaNMkGbF8NLa-CktIdOT8p-l95p"
ROLE_DATA_FILE = "role_staff_data.json"
HEADER_IMAGE_URL = "https://media.discordapp.net/attachments/1489674151634538656/1514681202789847111/52t36.png?ex=6a8494cc&is=6a83434c&hm=99f129bc5f55dad1eade6968c7690c951a57c177c6dfdaf527d3bbc5ea652bdd&=&format=webp&quality=lossless"


def load_role_data():
    try:
        with open(ROLE_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_role_data(data):
    with open(ROLE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_role_data(guild_id: int, role_id: int):
    data = load_role_data()
    guild_key = str(guild_id)
    role_key = str(role_id)

    if guild_key not in data:
        data[guild_key] = {}
    if role_key not in data[guild_key]:
        data[guild_key][role_key] = {
            "description": "Описание не установлено",
            "criteria": "Критерии не установлены"
        }
        save_role_data(data)

    return data[guild_key][role_key]


def set_role_description(guild_id: int, role_id: int, description: str):
    data = load_role_data()
    guild_key = str(guild_id)
    role_key = str(role_id)

    if guild_key not in data:
        data[guild_key] = {}
    if role_key not in data[guild_key]:
        data[guild_key][role_key] = {"criteria": "Критерии не установлены"}

    data[guild_key][role_key]["description"] = description
    save_role_data(data)
    return data[guild_key][role_key]


def set_role_criteria(guild_id: int, role_id: int, criteria: str):
    data = load_role_data()
    guild_key = str(guild_id)
    role_key = str(role_id)

    if guild_key not in data:
        data[guild_key] = {}
    if role_key not in data[guild_key]:
        data[guild_key][role_key] = {"description": "Описание не установлено"}

    data[guild_key][role_key]["criteria"] = criteria
    save_role_data(data)
    return data[guild_key][role_key]


class CriteriaButton(Button):
    def __init__(self, role_id: int, role_name: str):
        super().__init__(label="Критерии", style=discord.ButtonStyle.secondary, custom_id=f"criteria_{role_id}")
        self.role_id = role_id
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        role_data = get_role_data(interaction.guild.id, self.role_id)
        criteria_text = role_data.get("criteria", "Критерии не установлены")

        embed = discord.Embed(
            title=f"Критерии для роли: {self.role_name}",
            description=criteria_text,
            color=config.COLOR_INFO
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class StaffRequestView(discord.ui.View):
    def __init__(self, guild_id: int, roles_data: dict):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        for role_id, role_info in roles_data.items():
            role_name = role_info.get("name", "Неизвестная роль")
            btn = CriteriaButton(int(role_id), role_name)
            self.add_item(btn)


def build_staff_message_content(guild: discord.Guild):
    data = load_role_data()
    guild_key = str(guild.id)
    roles_data = data.get(guild_key, {})

    main_content = "Тут вы можите подать заявку на роль если подходите \nпо критериям команды нашего сервера. \n"

    return main_content, roles_data


async def send_or_update_webhook_message_json(webhook_url, guild: discord.Guild, message_id: str = None):
    main_content, roles_data = build_staff_message_content(guild)

    components = []
    for role_id, role_info in roles_data.items():
        desc = role_info.get('description', 'Описание не установлено')
        components.append({
            "type": 1,
            "components": [
                {
                    "type": 10,
                    "content": f"**{desc}** **:**\n<@&{role_id}> "
                }
            ],
            "accessory": {
                "type": 2,
                "style": 3,
                "label": "Критерии",
                "custom_id": f"p_{role_id}"
            }
        })

    json_payload = {
        "flags": 32768,
        "content": "> **Доступные роли:**\n" + main_content,
        "embeds": [
            {
                "image": {
                    "url": HEADER_IMAGE_URL
                },
                "color": 3066993
            }
        ],
        "components": components
    }

    try:
        async with aiohttp.ClientSession() as session:
            if message_id:
                url = f"{webhook_url}/messages/{message_id}"
                async with session.patch(url, json=json_payload) as response:
                    if response.status != 200:
                        print(f"Ошибка обновления: {response.status} - {await response.text()}")
                        return None
                    return message_id
            else:
                async with session.post(webhook_url, json=json_payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("id")
                    else:
                        print(f"Ошибка отправки: {response.status} - {await response.text()}")
                        return None
    except Exception as e:
        print(f"Ошибка при работе с вебхуком: {e}")
        return None

    return None


class StaffRequests(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.webhook_url = WEBHOOK_URL

    @app_commands.command(name="setstaffrequest", description="Настроить канал для заявок на staff роли")
    @app_commands.describe(channel="Канал для заявок на staff")
    async def setstaffrequest(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not has_full_access(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)

        await interaction.response.send_message(
            f"Сообщение для заявок отправлено в {channel.mention}",
            ephemeral=True
        )

        try:
            message_id = await send_or_update_webhook_message_json(self.webhook_url, interaction.guild, None)
            if message_id:
                storage.set_config(interaction.guild.id, staff_request_channel=channel.id, staff_request_message_id=message_id)
        except Exception as e:
            await interaction.followup.send(f"Ошибка при отправке вебхука: {e}", ephemeral=True)
            return

    @app_commands.command(name="cngroledesc", description="Изменить описание роли для заявки")
    @app_commands.describe(role="Роль, описание которой нужно изменить", new_description="Новое описание роли")
    async def cngroledesc(self, interaction: discord.Interaction, role: discord.Role, new_description: str):
        if not has_full_access(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)

        set_role_description(interaction.guild.id, role.id, new_description)

        data = load_role_data()
        guild_key = str(interaction.guild.id)
        if guild_key not in data:
            data[guild_key] = {}
        data[guild_key][str(role.id)]["name"] = role.name
        save_role_data(data)

        await interaction.response.send_message(
            f"Описание для роли {role.mention} изменено на:\n||{new_description}||",
            ephemeral=True
        )

        await self._update_webhook_message(interaction.guild)

    @app_commands.command(name="cngrolecr", description="Изменить критерии роли для заявки")
    @app_commands.describe(role="Роль, критерии которой нужно изменить", new_criteria="Новые критерии роли")
    async def cngrolecr(self, interaction: discord.Interaction, role: discord.Role, new_criteria: str):
        if not has_full_access(interaction):
            return await deny(interaction, config.ADMIN_ONLY_MSG)

        set_role_criteria(interaction.guild.id, role.id, new_criteria)

        data = load_role_data()
        guild_key = str(interaction.guild.id)
        if guild_key not in data:
            data[guild_key] = {}
        data[guild_key][str(role.id)]["name"] = role.name
        save_role_data(data)

        await interaction.response.send_message(
            f"Критерии для роли {role.mention} изменены.",
            ephemeral=True
        )

        await self._update_webhook_message(interaction.guild)

    async def _update_webhook_message(self, guild: discord.Guild):
        cfg = storage.get_config(guild.id)
        channel_id = cfg.get("staff_request_channel")
        message_id = cfg.get("staff_request_message_id")
        if not channel_id or not message_id:
            return

        channel = guild.get_channel(int(channel_id))
        if not channel:
            return

        try:
            await send_or_update_webhook_message_json(self.webhook_url, guild, str(message_id))
        except Exception as e:
            print(f"Ошибка при обновлении сообщения: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("criteria_"):
                await interaction.response.defer(ephemeral=True)
            elif custom_id.startswith("p_"):
                role_id = int(custom_id.split("_")[1])
                role_data = get_role_data(interaction.guild.id, role_id)
                criteria_text = role_data.get("criteria", "Критерии не установлены")

                role = interaction.guild.get_role(role_id)
                role_name = role.name if role else "Неизвестная роль"

                embed = discord.Embed(
                    title=f"Критерии для роли: {role_name}",
                    description=criteria_text,
                    color=config.COLOR_INFO
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffRequests(bot))
