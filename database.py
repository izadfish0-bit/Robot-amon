import aiosqlite
import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Users
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                join_date TEXT,
                balance INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                is_blocked INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0
            )
        """)

        # Game Accounts (inventory)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                price INTEGER NOT NULL,
                account_info TEXT,
                status TEXT DEFAULT 'available',  -- available, pending, sold
                created_at TEXT,
                sold_at TEXT,
                sold_to INTEGER
            )
        """)

        # Orders
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_type TEXT NOT NULL,  -- game, vip, website
                product_code TEXT,
                amount INTEGER NOT NULL,
                receipt_file_id TEXT,
                status TEXT DEFAULT 'pending',  -- pending, approved, rejected, cancelled
                admin_note TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Support Tickets
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT,
                status TEXT DEFAULT 'open',  -- open, closed
                created_at TEXT,
                closed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Ticket Messages
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                message_text TEXT,
                file_id TEXT,
                file_type TEXT,  -- photo, document, voice, video, text
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        """)

        # Discount / Referral Codes
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT DEFAULT 'percent',  -- percent, fixed
                discount_value INTEGER NOT NULL,
                max_uses INTEGER DEFAULT 1,
                used_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                expires_at TEXT
            )
        """)

        # Settings (key-value)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Transaction logs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TEXT
            )
        """)

        await db.commit()

        # Default settings
        await set_setting("vip_channel_link", "https://t.me/+YourPrivateChannelInvite")
        await set_setting("welcome_message", "به ربات رسمی برند AMON خوش آمدید ⚡")


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default


# ==================== USERS ====================
async def add_user(user_id: int, username: str = None, full_name: str = None, referred_by: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # Generate unique referral code
        import random, string
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Check uniqueness
        while True:
            async with db.execute("SELECT 1 FROM users WHERE referral_code = ?", (ref_code,)) as c:
                if not await c.fetchone():
                    break
            ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        now = datetime.datetime.now().isoformat()
        try:
            await db.execute("""
                INSERT INTO users (user_id, username, full_name, join_date, referral_code, referred_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, full_name, now, ref_code, referred_by))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # User already exists, update username/fullname
            await db.execute("""
                UPDATE users SET username = ?, full_name = ? WHERE user_id = ?
            """, (username, full_name, user_id))
            await db.commit()
            return False


async def get_user(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def is_blocked(user_id: int) -> bool:
    user = await get_user(user_id)
    return user and user.get("is_blocked", 0) == 1


async def block_user(user_id: int, block: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (1 if block else 0, user_id))
        await db.commit()


async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def add_spent(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def get_all_users() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY join_date DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_user_by_ref_code(code: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE referral_code = ?", (code.upper(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ==================== GAME ACCOUNTS ====================
async def add_game_account(code: str, price: int, account_info: str = "") -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        try:
            await db.execute("""
                INSERT INTO game_accounts (code, price, account_info, status, created_at)
                VALUES (?, ?, ?, 'available', ?)
            """, (code.strip(), price, account_info, now))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_game_account(code: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM game_accounts WHERE code = ?", (code.strip(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_game_account_status(code: str, status: str, sold_to: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        if status == "sold":
            await db.execute("""
                UPDATE game_accounts SET status = ?, sold_at = ?, sold_to = ? WHERE code = ?
            """, (status, now, sold_to, code.strip()))
        else:
            await db.execute("UPDATE game_accounts SET status = ? WHERE code = ?", (status, code.strip()))
        await db.commit()


async def set_account_info(code: str, info: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE game_accounts SET account_info = ? WHERE code = ?", (info, code.strip()))
        await db.commit()


async def get_available_accounts() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM game_accounts WHERE status = 'available' ORDER BY code") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_accounts() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM game_accounts ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_game_account(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM game_accounts WHERE code = ? AND status = 'available'", (code.strip(),))
        await db.commit()
        return cursor.rowcount > 0


# ==================== ORDERS ====================
async def create_order(user_id: int, order_type: str, amount: int, product_code: str = None, receipt_file_id: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute("""
            INSERT INTO orders (user_id, order_type, product_code, amount, receipt_file_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (user_id, order_type, product_code, amount, receipt_file_id, now, now))
        await db.commit()
        return cursor.lastrowid


async def update_order_status(order_id: int, status: str, admin_note: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        if admin_note:
            await db.execute("""
                UPDATE orders SET status = ?, admin_note = ?, updated_at = ? WHERE id = ?
            """, (status, admin_note, now, order_id))
        else:
            await db.execute("""
                UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
            """, (status, now, order_id))
        await db.commit()


async def update_order_receipt(order_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("""
            UPDATE orders SET receipt_file_id = ?, updated_at = ? WHERE id = ?
        """, (file_id, now, order_id))
        await db.commit()


async def get_order(order_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_orders(user_id: int) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_pending_orders() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT o.*, u.username, u.full_name 
            FROM orders o 
            LEFT JOIN users u ON o.user_id = u.user_id 
            WHERE o.status = 'pending' 
            ORDER BY o.created_at ASC
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_orders_stats() -> Dict:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'") as c:
            stats["pending"] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'approved'") as c:
            stats["approved"] = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders WHERE status = 'rejected'") as c:
            stats["rejected"] = (await c.fetchone())[0]
        async with db.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'approved'") as c:
            stats["total_revenue"] = (await c.fetchone())[0]
        return stats


# ==================== TICKETS ====================
async def create_ticket(user_id: int, subject: str = "پشتیبانی") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute("""
            INSERT INTO tickets (user_id, subject, status, created_at)
            VALUES (?, ?, 'open', ?)
        """, (user_id, subject, now))
        await db.commit()
        return cursor.lastrowid


async def add_ticket_message(ticket_id: int, sender_id: int, text: str = None, file_id: str = None, file_type: str = "text"):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("""
            INSERT INTO ticket_messages (ticket_id, sender_id, message_text, file_id, file_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticket_id, sender_id, text, file_id, file_type, now))
        await db.commit()


async def get_open_ticket(user_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM tickets WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def close_ticket(ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("UPDATE tickets SET status = 'closed', closed_at = ? WHERE id = ?", (now, ticket_id))
        await db.commit()


async def get_ticket(ticket_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ==================== DISCOUNT CODES ====================
async def add_discount_code(code: str, discount_type: str, value: int, max_uses: int = 1, expires_at: str = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        try:
            await db.execute("""
                INSERT INTO discount_codes (code, discount_type, discount_value, max_uses, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (code.upper(), discount_type, value, max_uses, now, expires_at))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_discount_code(code: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM discount_codes WHERE code = ? AND is_active = 1", (code.upper(),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def use_discount_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?
        """, (code.upper(),))
        await db.commit()


# ==================== LOGS ====================
async def add_log(user_id: int, action: str, details: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute("""
            INSERT INTO logs (user_id, action, details, created_at) VALUES (?, ?, ?, ?)
        """, (user_id, action, details, now))
        await db.commit()
