import os
from dotenv import load_dotenv

load_dotenv()

# ==================== BOT SETTINGS ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Admin IDs (can add more)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8007177524").split(",") if x.strip()]

# Payment Info
CARD_NUMBER = "6219861971517403"
CARD_NAME = "حجتی برندق"

# VIP Subscription
VIP_PRICE = 8_000_000  # تومان
VIP_CHANNEL_LINK = os.getenv("VIP_CHANNEL_LINK", "https://t.me/+YourPrivateChannelInvite")  # ادمین باید لینک واقعی رو بذاره

# Brand
BRAND_NAME = "AMON"
BRAND_EMOJI = "⚡"

# Database
DB_PATH = "amon_bot.db"

# Rate limiting (seconds)
RATE_LIMIT_SECONDS = 3

# Support
SUPPORT_USERNAME = "@Moein481"
SUPPORT_USER_ID = 8007177524

# ==================== FORCE JOIN CHANNELS ====================
# آیدی یا یوزرنیم کانال‌ها (بدون @ یا با @ فرقی ندارد)
# ربات باید ادمین این کانال‌ها باشد تا بتواند عضویت را چک کند
FORCE_JOIN_CHANNELS = [
    os.getenv("CHANNEL_1", "@AMON_Channel1"),
    os.getenv("CHANNEL_2", "@AMON_Channel2"),
    os.getenv("CHANNEL_3", "@AMON_Channel3"),
    os.getenv("CHANNEL_4", "@AMON_Channel4"),
]
