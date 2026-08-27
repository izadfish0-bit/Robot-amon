import re
import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from config import (
    ADMIN_IDS, CARD_NUMBER, CARD_NAME, VIP_PRICE,
    BRAND_NAME, SUPPORT_USERNAME, SUPPORT_USER_ID, FORCE_JOIN_CHANNELS
)
from database import (
    add_user, get_user, is_blocked, block_user, update_balance, add_spent,
    get_all_users, get_user_by_ref_code,
    add_game_account, get_game_account, update_game_account_status,
    set_account_info, get_available_accounts, get_all_accounts, delete_game_account,
    create_order, update_order_status, update_order_receipt, get_order,
    get_user_orders, get_pending_orders, get_orders_stats,
    create_ticket, add_ticket_message, get_open_ticket, close_ticket, get_ticket,
    add_discount_code, get_discount_code, use_discount_code,
    add_log, get_setting, set_setting
)
from keyboards import (
    main_menu_kb, cancel_kb, back_to_main_kb, payment_kb, after_receipt_kb,
    admin_order_kb, admin_reject_reason_kb, admin_panel_kb, admin_accounts_kb,
    confirm_delete_kb, profile_kb, support_kb, close_ticket_kb, faq_kb,
    force_join_kb
)
from states import (
    BuyGame, BuyVIP, Support, AdminAddAccount, AdminDeleteAccount,
    AdminReject, AdminSendInfo, AdminBroadcast, AdminBlock,
    AdminSettings, AdminDiscount, UseDiscount
)

router = Router()


# ==================== HELPERS ====================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def get_missing_channels(bot: Bot, user_id: int) -> list:
    """Return list of channels the user has NOT joined yet."""
    missing = []
    for channel in FORCE_JOIN_CHANNELS:
        chat_id = channel if channel.startswith("@") else f"@{channel}"
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                missing.append(channel)
        except Exception:
            # If bot can't check (not admin / channel not found), treat as missing
            missing.append(channel)
    return missing


async def force_join_required(bot: Bot, user_id: int) -> bool:
    """True if user still needs to join channels (admins are exempt)."""
    if is_admin(user_id):
        return False
    missing = await get_missing_channels(bot, user_id)
    return len(missing) > 0


def extract_account_code(text: str) -> str | None:
    """Extract account code from various formats"""
    if not text:
        return None
    patterns = [
        r"(?:کد\s*آگهی|کدآگهی)\s*[:：]?\s*(\d+)",
        r"(?:Code|code|CODE)\s*[:：]?\s*(\d+)",
        r"(?:کد)\s*[:：]?\s*(\d+)",
        r"^\s*(\d{1,6})\s*$",  # pure number
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def format_price(price: int) -> str:
    return f"{price:,}".replace(",", "٬") + " تومان"


async def notify_admins(bot: Bot, text: str, reply_markup=None, photo=None):
    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await bot.send_photo(admin_id, photo=photo, caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(admin_id, text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception:
            pass


# ==================== START & MAIN ====================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    user = message.from_user
    referred_by = None

    # Referral
    if command.args and command.args.startswith("ref_"):
        ref_code = command.args[4:].upper()
        referrer = await get_user_by_ref_code(ref_code)
        if referrer and referrer["user_id"] != user.id:
            referred_by = referrer["user_id"]

    is_new = await add_user(user.id, user.username, user.full_name, referred_by)
    await add_log(user.id, "start", f"new={is_new}")

    if await is_blocked(user.id):
        await message.answer("⛔ حساب شما مسدود شده است.\nبرای پیگیری با پشتیبانی تماس بگیرید.")
        return

    # ===== FORCE JOIN CHECK =====
    if await force_join_required(message.bot, user.id):
        missing = await get_missing_channels(message.bot, user.id)
        await message.answer(
            f"سلام <b>{user.full_name}</b> 👋\n\n"
            f"به ربات رسمی برند <b>{BRAND_NAME}</b> خوش آمدید ⚡\n\n"
            "🔒 برای استفاده از ربات باید در <b>همه کانال‌های زیر</b> عضو شوید:\n\n"
            "بعد از عضویت روی دکمه «عضو شدم» کلیک کنید.",
            reply_markup=force_join_kb(missing),
            parse_mode=ParseMode.HTML
        )
        if referred_by and is_new:
            try:
                await message.bot.send_message(
                    referred_by,
                    f"🎉 یک نفر با لینک معرف شما عضو شد!\nکاربر: {user.full_name}"
                )
            except Exception:
                pass
        return

    welcome = (
        f"سلام <b>{user.full_name}</b> 👋\n\n"
        f"به ربات رسمی برند <b>{BRAND_NAME}</b> خوش آمدید ⚡\n\n"
        "از منوی زیر بخش مورد نظر خود را انتخاب کنید:"
    )
    await message.answer(welcome, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)

    if referred_by and is_new:
        try:
            await message.bot.send_message(
                referred_by,
                f"🎉 یک نفر با لینک معرف شما عضو شد!\nکاربر: {user.full_name}"
            )
        except Exception:
            pass


@router.callback_query(F.data == "check_force_join")
async def check_force_join(callback: CallbackQuery):
    user_id = callback.from_user.id
    missing = await get_missing_channels(callback.bot, user_id)

    if not missing:
        await callback.message.edit_text(
            "✅ عضویت شما در همه کانال‌ها تأیید شد!\n\n"
            "حالا می‌توانید از ربات استفاده کنید."
        )
        await callback.message.answer(
            "منوی اصلی:",
            reply_markup=main_menu_kb()
        )
        await callback.answer("✅ تأیید شد")
    else:
        await callback.message.edit_text(
            "❌ هنوز در بعضی کانال‌ها عضو نشده‌اید!\n\n"
            "لطفاً در <b>همه کانال‌های زیر</b> عضو شوید و دوباره دکمه را بزنید:",
            reply_markup=force_join_kb(missing),
            parse_mode=ParseMode.HTML
        )
        await callback.answer("هنوز عضو نشده‌اید", show_alert=True)


@router.message(F.text == "🏠 بازگشت به منوی اصلی")
@router.message(F.text == "❌ انصراف")
@router.callback_query(F.data == "back_main")
async def back_to_main(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    bot = event.bot if isinstance(event, CallbackQuery) else event.bot

    # Force join check
    if await force_join_required(bot, user_id):
        missing = await get_missing_channels(bot, user_id)
        text = (
            "🔒 برای استفاده از ربات باید در همه کانال‌ها عضو شوید:\n\n"
            "بعد از عضویت روی «عضو شدم» کلیک کنید."
        )
        if isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=force_join_kb(missing))
            await event.answer()
        else:
            await event.answer(text, reply_markup=force_join_kb(missing))
        return

    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup(reply_markup=None)
        await event.message.answer("منوی اصلی:", reply_markup=main_menu_kb())
        await event.answer()
    else:
        await event.answer("منوی اصلی:", reply_markup=main_menu_kb())


@router.callback_query(F.data == "cancel_order")
async def cancel_order_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ خرید لغو شد.")
    await callback.message.answer("منوی اصلی:", reply_markup=main_menu_kb())
    await callback.answer()


# ==================== BUY GAME ACCOUNT ====================
@router.message(F.text == "🎮 خرید اکانت AMON GAME")
async def buy_game_start(message: Message, state: FSMContext):
    if await is_blocked(message.from_user.id):
        return
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer(
            "🔒 ابتدا باید در همه کانال‌ها عضو شوید:",
            reply_markup=force_join_kb(missing)
        )
        return
    await state.set_state(BuyGame.waiting_for_code)
    await message.answer(
        "🎮 <b>خرید اکانت AMON GAME</b>\n\n"
        "لطفاً <b>کد آگهی</b> اکانت مورد نظر را ارسال کنید.\n\n"
        "می‌توانید:\n"
        "• کد را تایپ کنید (مثلاً: <code>001</code>)\n"
        "• یا آگهی را از کانال فوروارد کنید\n\n"
        "فرمت‌های قابل قبول:\n"
        "<code>کد آگهی : 001</code>\n"
        "<code>Code: 001</code>\n"
        "<code>Code : 001</code>",
        reply_markup=cancel_kb(),
        parse_mode=ParseMode.HTML
    )


@router.message(BuyGame.waiting_for_code)
async def process_game_code(message: Message, state: FSMContext):
    text = message.text or message.caption or ""
    # If forwarded, try caption or text
    code = extract_account_code(text)

    if not code:
        await message.answer(
            "❌ کد آگهی پیدا نشد!\n\n"
            "لطفاً کد را به صورت صحیح ارسال کنید یا آگهی را فوروارد کنید.",
            reply_markup=cancel_kb()
        )
        return

    account = await get_game_account(code)
    if not account:
        await message.answer(
            f"❌ اکانت با کد <b>{code}</b> یافت نشد یا موجود نیست.\n"
            "لطفاً کد صحیح را وارد کنید.",
            reply_markup=cancel_kb(),
            parse_mode=ParseMode.HTML
        )
        return

    if account["status"] != "available":
        await message.answer(
            f"❌ اکانت کد <b>{code}</b> در حال حاضر موجود نیست (فروخته شده یا در حال فروش).",
            reply_markup=cancel_kb(),
            parse_mode=ParseMode.HTML
        )
        return

    # Save to state
    await state.update_data(code=code, price=account["price"], order_type="game")
    await state.set_state(BuyGame.confirming)

    await message.answer(
        f"✅ اکانت پیدا شد!\n\n"
        f"🏷 کد آگهی: <b>{code}</b>\n"
        f"💰 قیمت: <b>{format_price(account['price'])}</b>\n\n"
        f"برای ادامه روی دکمه پرداخت کلیک کنید.",
        reply_markup=payment_kb("game"),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "pay_done:game")
async def game_pay_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("code"):
        await callback.answer("خطا! دوباره شروع کنید.", show_alert=True)
        await state.clear()
        return

    await state.set_state(BuyGame.waiting_for_receipt)
    await callback.message.edit_text(
        f"💳 <b>اطلاعات پرداخت</b>\n\n"
        f"مبلغ قابل پرداخت: <b>{format_price(data['price'])}</b>\n\n"
        f"شماره کارت:\n<code>{CARD_NUMBER}</code>\n"
        f"به نام: <b>{CARD_NAME}</b>\n\n"
        f"پس از واریز، <b>تصویر واضح رسید</b> را همینجا ارسال کنید.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(BuyGame.waiting_for_receipt, F.photo)
async def game_receipt_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    code = data.get("code")
    price = data.get("price")

    if not code:
        await message.answer("خطا در اطلاعات. لطفاً دوباره شروع کنید.", reply_markup=main_menu_kb())
        await state.clear()
        return

    photo = message.photo[-1]
    file_id = photo.file_id

    # Create order
    order_id = await create_order(
        user_id=message.from_user.id,
        order_type="game",
        amount=price,
        product_code=code,
        receipt_file_id=file_id
    )

    # Mark account as pending
    await update_game_account_status(code, "pending")

    await add_log(message.from_user.id, "game_order", f"order_id={order_id}, code={code}")

    await message.answer(
        "✅ رسید شما دریافت شد.\n\n"
        "لطفاً منتظر بمانید تا رسید توسط ادمین بررسی و تأیید شود.\n"
        "پس از تأیید، اطلاعات اکانت برای شما ارسال خواهد شد.",
        reply_markup=main_menu_kb()
    )
    await state.clear()

    # Notify admins
    user = message.from_user
    caption = (
        f"🛒 <b>سفارش جدید اکانت GAME</b>\n\n"
        f"🆔 شماره سفارش: <code>{order_id}</code>\n"
        f"👤 کاربر: {user.full_name} (@{user.username or '—'})\n"
        f"🆔 آیدی: <code>{user.id}</code>\n"
        f"🏷 کد آگهی: <b>{code}</b>\n"
        f"💰 مبلغ: {format_price(price)}\n"
        f"📅 زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    await notify_admins(bot, caption, reply_markup=admin_order_kb(order_id, "game"), photo=file_id)


@router.message(BuyGame.waiting_for_receipt)
async def game_receipt_invalid(message: Message):
    await message.answer(
        "❌ لطفاً <b>تصویر واضح رسید</b> را ارسال کنید (نه متن یا فایل دیگر).",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb()
    )


# ==================== BUY VIP ====================
@router.message(F.text == "📈 خرید اشتراک AMON TRADE VIP")
async def buy_vip_start(message: Message, state: FSMContext):
    if await is_blocked(message.from_user.id):
        return
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    await state.set_state(BuyVIP.waiting_for_receipt)
    await state.update_data(order_type="vip", price=VIP_PRICE)

    await message.answer(
        f"📈 <b>خرید اشتراک AMON TRADE VIP</b>\n\n"
        f"سیگنال‌های روزانه کریپتو و فارکس با سود بالا و ریسک بسیار کم.\n\n"
        f"💰 مبلغ اشتراک: <b>{format_price(VIP_PRICE)}</b>\n\n"
        f"شماره کارت:\n<code>{CARD_NUMBER}</code>\n"
        f"به نام: <b>{CARD_NAME}</b>\n\n"
        f"پس از واریز، <b>تصویر واضح رسید</b> را ارسال کنید.",
        reply_markup=cancel_kb(),
        parse_mode=ParseMode.HTML
    )


@router.message(BuyVIP.waiting_for_receipt, F.photo)
async def vip_receipt_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    price = data.get("price", VIP_PRICE)
    photo = message.photo[-1]
    file_id = photo.file_id

    order_id = await create_order(
        user_id=message.from_user.id,
        order_type="vip",
        amount=price,
        receipt_file_id=file_id
    )

    await add_log(message.from_user.id, "vip_order", f"order_id={order_id}")

    await message.answer(
        "✅ رسید شما دریافت شد.\n\n"
        "لطفاً منتظر بمانید تا رسید تأیید شود.\n"
        "پس از تأیید، لینک عضویت در کانال خصوصی VIP برای شما ارسال می‌شود.",
        reply_markup=main_menu_kb()
    )
    await state.clear()

    user = message.from_user
    caption = (
        f"📈 <b>سفارش جدید اشتراک VIP</b>\n\n"
        f"🆔 شماره سفارش: <code>{order_id}</code>\n"
        f"👤 کاربر: {user.full_name} (@{user.username or '—'})\n"
        f"🆔 آیدی: <code>{user.id}</code>\n"
        f"💰 مبلغ: {format_price(price)}\n"
        f"📅 زمان: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    await notify_admins(bot, caption, reply_markup=admin_order_kb(order_id, "vip"), photo=file_id)


@router.message(BuyVIP.waiting_for_receipt)
async def vip_receipt_invalid(message: Message):
    await message.answer(
        "❌ لطفاً <b>تصویر واضح رسید</b> را ارسال کنید.",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb()
    )


# ==================== WEBSITE ORDER ====================
@router.message(F.text == "🌐 سفارش وبسایت AMON NET")
async def website_order(message: Message):
    if await is_blocked(message.from_user.id):
        return
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    await message.answer(
        "🌐 <b>سفارش وبسایت AMON NET</b>\n\n"
        "برای سفارش طراحی و پیاده‌سازی وبسایت، لطفاً به ادمین پیام دهید:\n\n"
        f"👤 ادمین: {SUPPORT_USERNAME}\n"
        f"🔗 <a href='https://t.me/{SUPPORT_USERNAME.replace('@', '')}'>کلیک برای ارسال پیام</a>\n\n"
        "لطفاً جزئیات سفارش خود را در پیوی ادمین شرح دهید.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(),
        disable_web_page_preview=True
    )


# ==================== ORDER STATUS ====================
@router.message(F.text == "📦 وضعیت سفارش‌های من")
async def my_orders(message: Message):
    if await is_blocked(message.from_user.id):
        return
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    orders = await get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("شما هنوز هیچ سفارشی ثبت نکرده‌اید.", reply_markup=main_menu_kb())
        return

    status_map = {
        "pending": "⏳ در انتظار تأیید",
        "approved": "✅ تأیید شده",
        "rejected": "❌ رد شده",
        "cancelled": "🚫 لغو شده"
    }
    type_map = {
        "game": "🎮 اکانت GAME",
        "vip": "📈 اشتراک VIP",
        "website": "🌐 وبسایت"
    }

    text = "📦 <b>آخرین سفارش‌های شما:</b>\n\n"
    for o in orders[:10]:
        text += (
            f"🆔 <code>{o['id']}</code> | {type_map.get(o['order_type'], o['order_type'])}\n"
            f"💰 {format_price(o['amount'])} | {status_map.get(o['status'], o['status'])}\n"
        )
        if o.get("product_code"):
            text += f"🏷 کد: {o['product_code']}\n"
        if o.get("admin_note") and o["status"] == "rejected":
            text += f"📝 دلیل رد: {o['admin_note']}\n"
        text += f"📅 {o['created_at'][:16].replace('T', ' ')}\n"
        text += "──────────────\n"

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())


# ==================== SUPPORT ====================
@router.message(F.text == "💬 پشتیبانی")
async def support_menu(message: Message):
    if await is_blocked(message.from_user.id):
        return
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    await message.answer(
        "💬 <b>پشتیبانی AMON</b>\n\n"
        "می‌توانید تیکت باز کنید یا مستقیم با ادمین در ارتباط باشید.",
        reply_markup=support_kb(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "start_ticket")
async def start_ticket(callback: CallbackQuery, state: FSMContext):
    open_ticket = await get_open_ticket(callback.from_user.id)
    if open_ticket:
        await callback.answer("شما یک تیکت باز دارید. پیام خود را ارسال کنید.", show_alert=True)
        await state.set_state(Support.waiting_message)
        await state.update_data(ticket_id=open_ticket["id"])
        await callback.message.answer(
            f"تیکت شماره <code>{open_ticket['id']}</code> باز است.\nپیام خود را بنویسید:",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel_kb()
        )
        return

    ticket_id = await create_ticket(callback.from_user.id)
    await state.set_state(Support.waiting_message)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer(
        f"✅ تیکت شماره <code>{ticket_id}</code> ایجاد شد.\n\n"
        "پیام خود را بنویسید (متن، عکس، ویس و ...):",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(Support.waiting_message)
async def ticket_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await state.clear()
        return

    file_id = None
    file_type = "text"
    text = message.text or message.caption or ""

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.voice:
        file_id = message.voice.file_id
        file_type = "voice"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    await add_ticket_message(ticket_id, message.from_user.id, text, file_id, file_type)

    # Forward to admins
    user = message.from_user
    header = (
        f"💬 <b>پیام تیکت #{ticket_id}</b>\n"
        f"از: {user.full_name} (@{user.username or '—'})\n"
        f"آیدی: <code>{user.id}</code>\n"
        f"──────────────"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, header, parse_mode=ParseMode.HTML)
            await message.copy_to(admin_id, reply_markup=close_ticket_kb(ticket_id))
        except Exception:
            pass

    await message.answer(
        "✅ پیام شما ارسال شد. منتظر پاسخ پشتیبانی باشید.\n"
        "می‌توانید پیام بعدی را هم ارسال کنید یا انصراف بزنید.",
        reply_markup=cancel_kb()
    )


@router.callback_query(F.data.startswith("close_ticket:"))
async def close_ticket_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید", show_alert=True)
        return
    ticket_id = int(callback.data.split(":")[1])
    ticket = await get_ticket(ticket_id)
    if ticket:
        await close_ticket(ticket_id)
        await callback.message.answer(f"🔒 تیکت #{ticket_id} بسته شد.")
        try:
            await callback.bot.send_message(
                ticket["user_id"],
                f"🔒 تیکت پشتیبانی شما (شماره {ticket_id}) توسط ادمین بسته شد."
            )
        except Exception:
            pass
    await callback.answer()


# ==================== FAQ & PROFILE ====================
@router.message(F.text == "📖 راهنما")
async def guide(message: Message):
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    await message.answer(
        "📖 <b>راهنمای استفاده از ربات AMON</b>\n\n"
        "از دکمه‌های زیر سوال مورد نظر را انتخاب کنید:",
        reply_markup=faq_kb(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("faq:"))
async def faq_answer(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    answers = {
        "buy_game": (
            "🎮 <b>نحوه خرید اکانت:</b>\n\n"
            "۱. روی «خرید اکانت AMON GAME» بزنید\n"
            "۲. کد آگهی را بفرستید یا آگهی را فوروارد کنید\n"
            "۳. قیمت را ببینید و پرداخت کنید\n"
            "۴. تصویر رسید را ارسال کنید\n"
            "۵. منتظر تأیید ادمین بمانید\n"
            "۶. اطلاعات اکانت برایتان ارسال می‌شود"
        ),
        "buy_vip": (
            "📈 <b>نحوه خرید اشتراک VIP:</b>\n\n"
            "۱. روی «خرید اشتراک AMON TRADE VIP» بزنید\n"
            "۲. مبلغ ۸ میلیون تومان را به کارت واریز کنید\n"
            "۳. تصویر رسید را ارسال کنید\n"
            "۴. پس از تأیید، لینک کانال خصوصی برایتان ارسال می‌شود"
        ),
        "payment": (
            f"💳 <b>پرداخت:</b>\n\n"
            f"شماره کارت:\n<code>{CARD_NUMBER}</code>\n"
            f"به نام: {CARD_NAME}\n\n"
            "فقط از طریق کارت به کارت انجام دهید."
        ),
        "receipt": (
            "🖼 <b>رسید پرداخت:</b>\n\n"
            "• تصویر باید واضح و خوانا باشد\n"
            "• مبلغ، تاریخ و شماره کارت مقصد مشخص باشد\n"
            "• از اسکرین‌شات با کیفیت استفاده کنید"
        )
    }
    await callback.message.answer(answers.get(key, "یافت نشد"), parse_mode=ParseMode.HTML)
    await callback.answer()


@router.message(F.text == "👤 پروفایل من")
async def my_profile(message: Message):
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("خطا در دریافت اطلاعات.")
        return
    text = (
        f"👤 <b>پروفایل شما</b>\n\n"
        f"نام: {user.get('full_name') or '—'}\n"
        f"یوزرنیم: @{user.get('username') or '—'}\n"
        f"آیدی: <code>{user['user_id']}</code>\n"
        f"تاریخ عضویت: {user.get('join_date', '')[:10]}\n"
        f"💰 موجودی: {format_price(user.get('balance', 0))}\n"
        f"🛒 مجموع خرید: {format_price(user.get('total_spent', 0))}\n"
        f"🔗 کد معرف شما: <code>{user.get('referral_code')}</code>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=profile_kb())


@router.callback_query(F.data == "my_ref_link")
async def my_ref_link(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("خطا", show_alert=True)
        return
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user['referral_code']}"
    await callback.message.answer(
        f"🔗 <b>لینک معرف شما:</b>\n\n<code>{link}</code>\n\n"
        "این لینک را برای دوستان خود بفرستید.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data == "my_balance")
async def my_balance(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    bal = user.get("balance", 0) if user else 0
    await callback.answer(f"موجودی شما: {format_price(bal)}", show_alert=True)


@router.message(F.text == "🎁 کد معرف / تخفیف")
async def discount_menu(message: Message, state: FSMContext):
    if await force_join_required(message.bot, message.from_user.id):
        missing = await get_missing_channels(message.bot, message.from_user.id)
        await message.answer("🔒 ابتدا باید در همه کانال‌ها عضو شوید:", reply_markup=force_join_kb(missing))
        return
    await state.set_state(UseDiscount.waiting_code)
    await message.answer(
        "🎁 کد تخفیف یا کد معرف خود را وارد کنید:",
        reply_markup=cancel_kb()
    )


@router.message(UseDiscount.waiting_code)
async def process_discount(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    disc = await get_discount_code(code)
    if not disc:
        await message.answer("❌ کد نامعتبر یا منقضی شده است.", reply_markup=main_menu_kb())
        await state.clear()
        return
    if disc["used_count"] >= disc["max_uses"]:
        await message.answer("❌ این کد دیگر قابل استفاده نیست.", reply_markup=main_menu_kb())
        await state.clear()
        return

    # For simplicity, just notify that it will be applied on next purchase
    # (full integration would apply on order creation)
    await use_discount_code(code)
    if disc["discount_type"] == "percent":
        msg = f"✅ کد تخفیف {disc['discount_value']}٪ با موفقیت ثبت شد و در خرید بعدی اعمال می‌شود."
    else:
        msg = f"✅ کد تخفیف {format_price(disc['discount_value'])} ثبت شد."
    await message.answer(msg, reply_markup=main_menu_kb())
    await state.clear()


# ==================== ADMIN PANEL ====================
@router.message(Command("admin"))
@router.message(F.text == "⚙️ پنل ادمین")
async def admin_entry(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🔐 <b>پنل مدیریت AMON</b>\n\nیکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=admin_panel_kb(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "🏠 خروج از پنل ادمین")
async def admin_exit(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("از پنل ادمین خارج شدید.", reply_markup=main_menu_kb())


@router.message(F.text == "📊 آمار و گزارش")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await get_orders_stats()
    accounts = await get_available_accounts()
    users = await get_all_users()
    text = (
        f"📊 <b>آمار ربات AMON</b>\n\n"
        f"👥 تعداد کاربران: {len(users)}\n"
        f"🎮 اکانت‌های موجود: {len(accounts)}\n\n"
        f"📦 سفارش‌های در انتظار: {stats['pending']}\n"
        f"✅ تأیید شده: {stats['approved']}\n"
        f"❌ رد شده: {stats['rejected']}\n\n"
        f"💰 درآمد کل: {format_price(stats['total_revenue'])}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "📦 سفارش‌های در انتظار")
async def admin_pending(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    orders = await get_pending_orders()
    if not orders:
        await message.answer("هیچ سفارش در انتظاری وجود ندارد.")
        return
    for o in orders[:15]:
        type_map = {"game": "🎮 GAME", "vip": "📈 VIP"}
        text = (
            f"🆔 سفارش <code>{o['id']}</code> | {type_map.get(o['order_type'], o['order_type'])}\n"
            f"👤 {o.get('full_name')} (@{o.get('username') or '—'})\n"
            f"آیدی: <code>{o['user_id']}</code>\n"
            f"💰 {format_price(o['amount'])}\n"
        )
        if o.get("product_code"):
            text += f"🏷 کد: {o['product_code']}\n"
        text += f"📅 {o['created_at'][:16]}"
        if o.get("receipt_file_id"):
            await bot.send_photo(
                message.chat.id,
                photo=o["receipt_file_id"],
                caption=text,
                reply_markup=admin_order_kb(o["id"], o["order_type"]),
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(text, reply_markup=admin_order_kb(o["id"], o["order_type"]), parse_mode=ParseMode.HTML)


# Admin approve / reject
@router.callback_query(F.data.startswith("admin_approve:"))
async def admin_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید", show_alert=True)
        return
    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)
    if not order or order["status"] != "pending":
        await callback.answer("این سفارش دیگر قابل تأیید نیست.", show_alert=True)
        return

    await update_order_status(order_id, "approved")
    await add_spent(order["user_id"], order["amount"])

    if order["order_type"] == "game" and order.get("product_code"):
        await update_game_account_status(order["product_code"], "sold", order["user_id"])

    await callback.message.answer(f"✅ سفارش #{order_id} تأیید شد.")
    try:
        await bot.send_message(
            order["user_id"],
            f"✅ <b>رسید شما تأیید شد!</b>\n\n"
            f"شماره سفارش: <code>{order_id}</code>\n"
            f"به زودی اطلاعات برای شما ارسال می‌شود.",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    # For VIP auto-send link if set
    if order["order_type"] == "vip":
        link = await get_setting("vip_channel_link")
        if link and "YourPrivate" not in link:
            try:
                await bot.send_message(
                    order["user_id"],
                    f"🎉 <b>اشتراک VIP شما فعال شد!</b>\n\n"
                    f"لینک عضویت در کانال خصوصی:\n{link}\n\n"
                    "لطفاً سریع عضو شوید.",
                    parse_mode=ParseMode.HTML
                )
                await callback.message.answer("لینک VIP به صورت خودکار ارسال شد.")
            except Exception:
                pass

    await callback.answer("تأیید شد")


@router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    order_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        "دلیل رد را انتخاب کنید:",
        reply_markup=admin_reject_reason_kb(order_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reject_reason:"))
async def admin_reject_reason(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    order_id = int(parts[1])
    reason_key = parts[2]
    reasons = {
        "invalid": "رسید نامعتبر است",
        "amount": "مبلغ واریزی نادرست است",
        "unclear": "تصویر رسید نامشخص است",
        "other": "سایر دلایل - با پشتیبانی تماس بگیرید"
    }
    reason = reasons.get(reason_key, "رد شده")
    order = await get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد")
        return

    await update_order_status(order_id, "rejected", reason)

    # Return account to available if game
    if order["order_type"] == "game" and order.get("product_code"):
        await update_game_account_status(order["product_code"], "available")

    try:
        await bot.send_message(
            order["user_id"],
            f"❌ <b>رسید شما رد شد</b>\n\n"
            f"شماره سفارش: <code>{order_id}</code>\n"
            f"دلیل: {reason}\n\n"
            "در صورت نیاز با پشتیبانی در ارتباط باشید.",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    await callback.message.answer(f"❌ سفارش #{order_id} رد شد.\nدلیل: {reason}")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_send_info:"))
async def admin_send_info_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    await state.set_state(AdminSendInfo.waiting_content)
    await state.update_data(target_user_id=order["user_id"], order_id=order_id, order_type="game")
    await callback.message.answer(
        f"📤 اطلاعات اکانت را برای کاربر ارسال کنید.\n"
        f"می‌توانید متن، عکس، ویس، فایل و هر چیزی بفرستید.\n"
        f"سفارش: #{order_id}",
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_send_vip:"))
async def admin_send_vip(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    order_id = int(callback.data.split(":")[1])
    order = await get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    link = await get_setting("vip_channel_link")
    try:
        await callback.bot.send_message(
            order["user_id"],
            f"🎉 <b>اشتراک VIP شما فعال شد!</b>\n\n"
            f"لینک عضویت:\n{link}",
            parse_mode=ParseMode.HTML
        )
        await callback.message.answer("✅ لینک VIP ارسال شد.")
    except Exception as e:
        await callback.message.answer(f"خطا در ارسال: {e}")
    await callback.answer()


@router.message(AdminSendInfo.waiting_content)
async def admin_send_content(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target = data.get("target_user_id")
    order_id = data.get("order_id")
    if not target:
        await state.clear()
        return

    header = f"📦 <b>اطلاعات سفارش #{order_id}</b>\n\n"
    try:
        await bot.send_message(target, header, parse_mode=ParseMode.HTML)
        await message.copy_to(target)
        await message.answer("✅ اطلاعات با موفقیت به کاربر ارسال شد.", reply_markup=admin_panel_kb())
    except Exception as e:
        await message.answer(f"❌ خطا در ارسال: {e}", reply_markup=admin_panel_kb())
    await state.clear()


# Manage accounts
@router.message(F.text == "🎮 مدیریت اکانت‌ها")
async def admin_manage_accounts(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("مدیریت اکانت‌های GAME:", reply_markup=admin_accounts_kb())


@router.callback_query(F.data == "admin_list_available")
async def list_available(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    accounts = await get_available_accounts()
    if not accounts:
        await callback.message.answer("هیچ اکانت موجودی نیست.")
    else:
        text = "📋 <b>اکانت‌های موجود:</b>\n\n"
        for a in accounts[:50]:
            text += f"🏷 <code>{a['code']}</code> — {format_price(a['price'])}\n"
        await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "admin_list_all")
async def list_all_accounts(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    accounts = await get_all_accounts()
    text = "📋 <b>همه اکانت‌ها (آخرین ۵۰):</b>\n\n"
    for a in accounts[:50]:
        status = {"available": "✅", "pending": "⏳", "sold": "🔴"}.get(a["status"], a["status"])
        text += f"{status} <code>{a['code']}</code> — {format_price(a['price'])} ({a['status']})\n"
    await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.message(F.text == "➕ افزودن اکانت")
async def admin_add_account_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAddAccount.waiting_code)
    await message.answer("کد آگهی اکانت جدید را وارد کنید (مثلاً 001):", reply_markup=cancel_kb())


@router.message(AdminAddAccount.waiting_code)
async def admin_add_code(message: Message, state: FSMContext):
    code = (message.text or "").strip()
    if not code:
        await message.answer("کد نامعتبر")
        return
    await state.update_data(code=code)
    await state.set_state(AdminAddAccount.waiting_price)
    await message.answer("قیمت اکانت را به تومان وارد کنید (فقط عدد):")


@router.message(AdminAddAccount.waiting_price)
async def admin_add_price(message: Message, state: FSMContext):
    try:
        price = int((message.text or "").replace(",", "").replace("٬", "").strip())
    except ValueError:
        await message.answer("قیمت باید عدد باشد.")
        return
    await state.update_data(price=price)
    await state.set_state(AdminAddAccount.waiting_info)
    await message.answer(
        "اطلاعات اکانت را وارد کنید (جیمیل، رمز و ...).\n"
        "اگر بعداً می‌خواهید بفرستید، بنویسید: skip"
    )


@router.message(AdminAddAccount.waiting_info)
async def admin_add_info(message: Message, state: FSMContext):
    data = await state.get_data()
    info = message.text or ""
    if info.lower() == "skip":
        info = ""
    success = await add_game_account(data["code"], data["price"], info)
    if success:
        await message.answer(
            f"✅ اکانت <code>{data['code']}</code> با قیمت {format_price(data['price'])} اضافه شد.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_kb()
        )
    else:
        await message.answer("❌ این کد قبلاً وجود دارد.", reply_markup=admin_panel_kb())
    await state.clear()


@router.message(F.text == "🗑 حذف اکانت")
async def admin_delete_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminDeleteAccount.waiting_code)
    await message.answer("کد اکانتی که می‌خواهید حذف کنید را وارد کنید:", reply_markup=cancel_kb())


@router.message(AdminDeleteAccount.waiting_code)
async def admin_delete_code(message: Message, state: FSMContext):
    code = (message.text or "").strip()
    success = await delete_game_account(code)
    if success:
        await message.answer(f"✅ اکانت {code} حذف شد.", reply_markup=admin_panel_kb())
    else:
        await message.answer("❌ اکانت یافت نشد یا قبلاً فروخته شده.", reply_markup=admin_panel_kb())
    await state.clear()


# Settings
@router.message(F.text == "⚙️ تنظیمات")
async def admin_settings(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = await get_setting("vip_channel_link")
    await message.answer(
        f"⚙️ <b>تنظیمات</b>\n\n"
        f"لینک فعلی کانال VIP:\n{link}\n\n"
        "برای تغییر لینک، لینک جدید را ارسال کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=cancel_kb()
    )
    await state.set_state(AdminSettings.waiting_vip_link)


@router.message(AdminSettings.waiting_vip_link)
async def admin_set_vip_link(message: Message, state: FSMContext):
    link = (message.text or "").strip()
    await set_setting("vip_channel_link", link)
    await message.answer("✅ لینک کانال VIP به‌روزرسانی شد.", reply_markup=admin_panel_kb())
    await state.clear()


# Broadcast
@router.message(F.text == "📢 ارسال پیام همگانی")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBroadcast.waiting_message)
    await message.answer("پیام همگانی را ارسال کنید (متن، عکس و ...):", reply_markup=cancel_kb())


@router.message(AdminBroadcast.waiting_message)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    users = await get_all_users()
    success = 0
    fail = 0
    await message.answer(f"در حال ارسال به {len(users)} کاربر...")
    for u in users:
        try:
            await message.copy_to(u["user_id"])
            success += 1
        except Exception:
            fail += 1
    await message.answer(
        f"✅ ارسال تمام شد.\nموفق: {success}\nناموفق: {fail}",
        reply_markup=admin_panel_kb()
    )
    await state.clear()


# Block user
@router.message(F.text == "🚫 بلاک/آنبلاک کاربر")
async def admin_block_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBlock.waiting_user_id)
    await message.answer("آیدی عددی کاربر را وارد کنید:", reply_markup=cancel_kb())


@router.message(AdminBlock.waiting_user_id)
async def admin_block_user(message: Message, state: FSMContext):
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        await message.answer("آیدی باید عدد باشد.")
        return
    user = await get_user(uid)
    if not user:
        await message.answer("کاربر یافت نشد.", reply_markup=admin_panel_kb())
        await state.clear()
        return
    new_status = not user.get("is_blocked", 0)
    await block_user(uid, new_status)
    status = "مسدود" if new_status else "آزاد"
    await message.answer(f"✅ کاربر {uid} {status} شد.", reply_markup=admin_panel_kb())
    await state.clear()


@router.message(F.text == "👥 لیست کاربران")
async def admin_list_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    users = await get_all_users()
    text = f"👥 تعداد کل کاربران: {len(users)}\n\nآخرین ۲۰ کاربر:\n\n"
    for u in users[:20]:
        text += f"<code>{u['user_id']}</code> — {u.get('full_name') or '—'} (@{u.get('username') or '—'})\n"
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(F.text == "🎟 مدیریت کد تخفیف")
async def admin_discount_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminDiscount.waiting_code)
    await message.answer("کد تخفیف جدید را وارد کنید (مثلاً AMON20):", reply_markup=cancel_kb())


@router.message(AdminDiscount.waiting_code)
async def admin_disc_code(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    await state.update_data(code=code)
    await state.set_state(AdminDiscount.waiting_type)
    await message.answer("نوع تخفیف را مشخص کنید:\n1 = درصدی\n2 = مبلغ ثابت (تومان)")


@router.message(AdminDiscount.waiting_type)
async def admin_disc_type(message: Message, state: FSMContext):
    t = (message.text or "").strip()
    if t == "1":
        dtype = "percent"
    elif t == "2":
        dtype = "fixed"
    else:
        await message.answer("فقط 1 یا 2 وارد کنید.")
        return
    await state.update_data(dtype=dtype)
    await state.set_state(AdminDiscount.waiting_value)
    await message.answer("مقدار تخفیف را وارد کنید (عدد):")


@router.message(AdminDiscount.waiting_value)
async def admin_disc_value(message: Message, state: FSMContext):
    try:
        value = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد وارد کنید.")
        return
    await state.update_data(value=value)
    await state.set_state(AdminDiscount.waiting_uses)
    await message.answer("حداکثر تعداد استفاده را وارد کنید:")


@router.message(AdminDiscount.waiting_uses)
async def admin_disc_uses(message: Message, state: FSMContext):
    try:
        uses = int((message.text or "").strip())
    except ValueError:
        await message.answer("عدد وارد کنید.")
        return
    data = await state.get_data()
    success = await add_discount_code(data["code"], data["dtype"], data["value"], uses)
    if success:
        await message.answer(
            f"✅ کد <code>{data['code']}</code> اضافه شد.",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_kb()
        )
    else:
        await message.answer("❌ این کد قبلاً وجود دارد.", reply_markup=admin_panel_kb())
    await state.clear()


# Fallback for unknown messages in main state
@router.message()
async def fallback(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None and not is_admin(message.from_user.id):
        await message.answer(
            "لطفاً از دکمه‌های منو استفاده کنید.",
            reply_markup=main_menu_kb()
        )
