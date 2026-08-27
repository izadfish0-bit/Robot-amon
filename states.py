from aiogram.fsm.state import State, StatesGroup


class BuyGame(StatesGroup):
    waiting_for_code = State()
    waiting_for_receipt = State()
    confirming = State()


class BuyVIP(StatesGroup):
    waiting_for_receipt = State()


class Support(StatesGroup):
    waiting_message = State()


class AdminAddAccount(StatesGroup):
    waiting_code = State()
    waiting_price = State()
    waiting_info = State()


class AdminDeleteAccount(StatesGroup):
    waiting_code = State()


class AdminReject(StatesGroup):
    waiting_reason = State()


class AdminSendInfo(StatesGroup):
    waiting_content = State()  # any media or text


class AdminBroadcast(StatesGroup):
    waiting_message = State()


class AdminBlock(StatesGroup):
    waiting_user_id = State()


class AdminSettings(StatesGroup):
    waiting_vip_link = State()


class AdminDiscount(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_value = State()
    waiting_uses = State()


class UseDiscount(StatesGroup):
    waiting_code = State()
