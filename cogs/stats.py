import discord
from discord.ext import commands, tasks

STATS_ROLE_ID = 1469719460364681239
STATS_CHANNEL_ID = 1540025437642555472
CHANNEL_NAME_FORMAT = "На сервере: {count}"


class MemberCountStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_channel_name.start()

    def cog_unload(self):
        self.update_channel_name.cancel()

    @tasks.loop(minutes=1)
    async def update_channel_name(self):
        channel = self.bot.get_channel(STATS_CHANNEL_ID)
        if channel is None:
            return
        guild = channel.guild
        role = guild.get_role(STATS_ROLE_ID)
        if role is None:
            return
        count = len(role.members)
        new_name = CHANNEL_NAME_FORMAT.format(count=count)
        if channel.name == new_name:
            return
        try:
            await channel.edit(name=new_name)
        except discord.HTTPException:
            pass

    @update_channel_name.before_loop
    async def before_update_channel_name(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberCountStats(bot))
