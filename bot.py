import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import router

# Force unbuffered logging (important for Railway)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)


async def main():
    # ===== TOKEN CHECK =====
    if not BOT_TOKEN or BOT_TOKEN.strip() in ("", "YOUR_BOT_TOKEN_HERE", "123456:ABC-DEF_your_bot_token_here"):
        logger.error("=" * 50)
        logger.error("BOT_TOKEN is missing or invalid!")
        logger.error("Set BOT_TOKEN in Railway Variables.")
        logger.error("=" * 50)
        # Keep process alive so Railway shows the error in logs instead of instant exit
        while True:
            await asyncio.sleep(60)
        return

    logger.info("Token loaded successfully (length=%d)", len(BOT_TOKEN))

    # ===== DATABASE =====
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.exception("Database init failed: %s", e)
        while True:
            await asyncio.sleep(60)
        return

    # ===== BOT & DISPATCHER =====
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # ===== DELETE WEBHOOK (critical for polling) =====
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully. Starting polling...")
    except Exception as e:
        logger.error("Failed to delete webhook: %s", e)

    # ===== GET BOT INFO =====
    try:
        me = await bot.get_me()
        logger.info("Bot started as @%s (id=%s)", me.username, me.id)
    except Exception as e:
        logger.exception("getMe failed – token is probably wrong: %s", e)
        while True:
            await asyncio.sleep(60)
        return

    # ===== START POLLING =====
    logger.info("Polling started. Waiting for updates...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.exception("Polling crashed: %s", e)
    finally:
        await bot.session.close()
        logger.info("Bot session closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        # Keep alive so error stays visible in Railway logs
        import time
        while True:
            time.sleep(60)
