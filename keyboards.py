from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import SUPPORT_USERNAME, FORCE_JOIN_CHANNELS


# ==================== FORCE JOIN ====================
def force_join_kb(missing_channels: list = None):
    """
    missing_channels: list of channel usernames that user has not joined yet.
    If None, show all channels.
    """
    channels = missing_channels if missing_channels is not None else FORCE_JOIN_CHANNELS
    buttons = []
    for i, ch in enumerate(channels, 1):
        username = ch.lstrip("@")
        buttons.append([
            InlineKeyboardButton(
                text=f"📢 عضویت در کانال {i}",
                url=f"https://t.me/{username}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="✅ عضو شدم — بررسی عضویت", callback_data="check_force_join")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== USER MAIN MENU ====================
def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 خرید اکانت AMON GAME")],
            [KeyboardButton(text="📈 خرید اشتراک AMON TRADE VIP")],
            [KeyboardButton(text="🌐 سفارش وبسایت AMON NET")],
            [
                KeyboardButton(text="📦 وضعیت سفارش‌های من"),
                KeyboardButton(text="💬 پشتیبانی")
            ],
            [
                KeyboardButton(text="📖 راهنما"),
                KeyboardButton(text="👤 پروفایل من")
            ],
            [KeyboardButton(text="🎁 کد معرف / تخفیف")]
        ],
        resize_keyboard=True,
        input_field_placeholder="از منوی زیر انتخاب کنید..."
    )


def cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ انصراف")]],
        resize_keyboard=True
    )


def back_to_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 بازگشت به منوی اصلی")]],
        resize_keyboard=True
    )


# ==================== PAYMENT ====================
def payment_kb(order_type: str = "game"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 پرداخت کردم و ارسال رسید", callback_data=f"pay_done:{order_type}")],
            [InlineKeyboardButton(text="❌ انصراف از خرید", callback_data="cancel_order")]
        ]
    )


def after_receipt_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back_main")]
        ]
    )


# ==================== ADMIN ORDER ACTIONS ====================
def admin_order_kb(order_id: int, order_type: str):
    buttons = [
        [
            InlineKeyboardButton(text="✅ تأیید رسید", callback_data=f"admin_approve:{order_id}"),
            InlineKeyboardButton(text="❌ رد رسید", callback_data=f"admin_reject:{order_id}")
        ]
    ]
    if order_type == "game":
        buttons.append([
            InlineKeyboardButton(text="📤 ارسال اطلاعات اکانت", callback_data=f"admin_send_info:{order_id}")
        ])
    elif order_type == "vip":
        buttons.append([
            InlineKeyboardButton(text="🔗 ارسال لینک VIP", callback_data=f"admin_send_vip:{order_id}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_reject_reason_kb(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="رسید نامعتبر", callback_data=f"reject_reason:{order_id}:invalid")],
            [InlineKeyboardButton(text="مبلغ نادرست", callback_data=f"reject_reason:{order_id}:amount")],
            [InlineKeyboardButton(text="تصویر نامشخص", callback_data=f"reject_reason:{order_id}:unclear")],
            [InlineKeyboardButton(text="سایر دلایل", callback_data=f"reject_reason:{order_id}:other")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"admin_order_back:{order_id}")]
        ]
    )


# ==================== ADMIN PANEL ====================
def admin_panel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 آمار و گزارش")],
            [
                KeyboardButton(text="📦 سفارش‌های در انتظار"),
                KeyboardButton(text="🎮 مدیریت اکانت‌ها")
            ],
            [
                KeyboardButton(text="➕ افزودن اکانت"),
                KeyboardButton(text="🗑 حذف اکانت")
            ],
            [
                KeyboardButton(text="🎟 مدیریت کد تخفیف"),
                KeyboardButton(text="⚙️ تنظیمات")
            ],
            [
                KeyboardButton(text="👥 لیست کاربران"),
                KeyboardButton(text="🚫 بلاک/آنبلاک کاربر")
            ],
            [KeyboardButton(text="📢 ارسال پیام همگانی")],
            [KeyboardButton(text="🏠 خروج از پنل ادمین")]
        ],
        resize_keyboard=True
    )


def admin_accounts_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 لیست اکانت‌های موجود", callback_data="admin_list_available")],
            [InlineKeyboardButton(text="📋 همه اکانت‌ها", callback_data="admin_list_all")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")]
        ]
    )


def confirm_delete_kb(code: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ بله حذف شود", callback_data=f"confirm_del:{code}"),
                InlineKeyboardButton(text="❌ خیر", callback_data="admin_back")
            ]
        ]
    )


# ==================== PROFILE & OTHERS ====================
def profile_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 لینک معرف من", callback_data="my_ref_link")],
            [InlineKeyboardButton(text="💰 موجودی کیف پول", callback_data="my_balance")]
        ]
    )


def support_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ شروع گفتگو با پشتیبانی", callback_data="start_ticket")],
            [InlineKeyboardButton(text="🔗 ارتباط مستقیم", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")]
        ]
    )


def close_ticket_kb(ticket_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔒 بستن تیکت", callback_data=f"close_ticket:{ticket_id}")]
        ]
    )


def faq_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="چطور اکانت بخرم؟", callback_data="faq:buy_game")],
            [InlineKeyboardButton(text="چطور اشتراک VIP بخرم؟", callback_data="faq:buy_vip")],
            [InlineKeyboardButton(text="پرداخت چطوریه؟", callback_data="faq:payment")],
            [InlineKeyboardButton(text="رسید چی باشه؟", callback_data="faq:receipt")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_main")]
        ]
    )
