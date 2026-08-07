import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
ALLOWED_ROLE_IDS = [
    int(rid.strip()) for rid in os.getenv("ALLOWED_ROLE_IDS", "").split(",") if rid.strip().isdigit()
]
report_role_env = os.getenv("REPORT_ROLE_ID")
REPORT_ROLE_ID = int(report_role_env) if report_role_env else 1518934599747637288
WARNING_BANNER_URL = os.getenv(
    "WARNING_BANNER_URL",
    "https://cdn.discordapp.com/attachments/1489674151634538656/1523645578721099816/warning.png",
)

NO_PERMISSION_MSG = "Ты слишком нищий чтобы использовать эту команду"
ADMIN_ONLY_MSG = "Только администраторы могут использовать эту команду."

COLOR_OK = 0x43B581
COLOR_WARN = 0xFAA61A
COLOR_ERR = 0xE84343
COLOR_INFO = 0x5865F2
COLOR_NEUTRAL = 0x2B2D31

MAX_TIMEOUT = timedelta(days=28)