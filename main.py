import asyncio
import os
import random
import time
from pathlib import Path

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# 🚀 СВАГА БОТ — MERGED EDITION
# Что внутри:
# - SQLite база
# - рефералка
# - промокод
# - работы
# - города
# - реальные фоны городов
# - профиль со стикменом на фоне города
# - авто с автозагрузкой из папки assets/cars
# - ЦУМ с превью одежды
# - шкаф / надеть вещи
# - казино / рулетка / кости
# - дома
# - админка
#
# ВАЖНО ПО ФАЙЛАМ:
# 1) Положи фотки городов сюда:
#    assets/cities/Кашира.jpg
#    assets/cities/Ступино.jpg
#    assets/cities/Новосёлки.jpg
#    или .png / .jpeg / .webp
#
# 2) Машины:
#    assets/cars/*.png
#    Имена файлов можно делать так:
#    vaz.png, bmw_m5.png, g63.png и т.д.
#
# 3) Одежда:
#    assets/clothes/hat/*.png
#    assets/clothes/top/*.png
#    assets/clothes/pants/*.png
#    assets/clothes/shoes/*.png
#
#    Пример имени:
#    nike_black_hat.png
#    zara_white_top.png
#    levis_blue_pants.png
#    airforce_white_shoes.png
#
# 4) Если картинки вещей реально есть, они будут:
#    - показываться в ЦУМ как превью
#    - по возможности накладываться на персонажа
#
# 5) Там, где у тебя были "фотки городов со стикменом",
#    этот код сам рисует стикмена поверх реального фона.
# ============================================================

BOT_TOKEN = "YOUR_TOKEN"
DB_PATH = "swaga.db"
ADMIN_IDS = {8039924340}

START_BALANCE = 5000
PROMO_CODE = "English"
PROMO_REWARD = 222222
REF_REWARD = 25000
DEFAULT_CITY = "Кашира"

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CARS_DIR = ASSETS_DIR / "cars"
CITIES_DIR = ASSETS_DIR / "cities"
CLOTHES_DIR = ASSETS_DIR / "clothes"
RENDER_DIR = BASE_DIR / "renders"
RENDER_DIR.mkdir(exist_ok=True)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

last_msg = {}
banned = {}
pending_number_bet = {}
pending_promo = set()
pending_nickname = set()
pending_trade = {}

red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
black_numbers = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}


# ============================================================
# DB
# ============================================================
class DB:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(DB_PATH)
        self.conn.row_factory = aiosqlite.Row

        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 5000,
                nickname TEXT,
                last_nick_change INTEGER DEFAULT 0,
                exp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                city TEXT DEFAULT 'Кашира',
                car TEXT,
                house TEXT,
                referred_by INTEGER,
                promo_used INTEGER DEFAULT 0,
                job_cd INTEGER DEFAULT 0,
                last_daily_shop_refresh INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                slot TEXT NOT NULL,
                name TEXT NOT NULL,
                brand TEXT,
                color TEXT,
                price INTEGER DEFAULT 0,
                image_path TEXT,
                equipped INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY,
                item_type TEXT NOT NULL,
                slot TEXT NOT NULL,
                name TEXT NOT NULL,
                brand TEXT,
                color TEXT,
                price INTEGER NOT NULL,
                image_path TEXT,
                created_at INTEGER NOT NULL
            );
            """
        )
        await self.conn.commit()

    async def ensure_user(self, uid: int, ref: int | None = None):
        row = await self.fetchone("SELECT id FROM users WHERE id=?", (uid,))
        if row:
            return

        nickname = f"Player{uid}"
        await self.conn.execute(
            """
            INSERT INTO users (id, balance, nickname, city, referred_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uid, START_BALANCE, nickname, DEFAULT_CITY, ref),
        )

        if ref and ref != uid:
            ref_exists = await self.fetchone("SELECT id FROM users WHERE id=?", (ref,))
            if ref_exists:
                await self.conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE id=?",
                    (REF_REWARD, ref),
                )

        await self.conn.commit()

    async def execute(self, query: str, params=()):
        await self.conn.execute(query, params)
        await self.conn.commit()

    async def fetchone(self, query: str, params=()):
        cur = await self.conn.execute(query, params)
        return await cur.fetchone()

    async def fetchall(self, query: str, params=()):
        cur = await self.conn.execute(query, params)
        return await cur.fetchall()

    async def get_user(self, uid: int):
        return await self.fetchone("SELECT * FROM users WHERE id=?", (uid,))

    async def add_balance(self, uid: int, amount: int):
        await self.execute(
            "UPDATE users SET balance = balance + ? WHERE id=?",
            (amount, uid),
        )

    async def set_balance(self, uid: int, amount: int):
        await self.execute("UPDATE users SET balance=? WHERE id=?", (amount, uid))

    async def set_car(self, uid: int, car_name: str | None):
        await self.execute("UPDATE users SET car=? WHERE id=?", (car_name, uid))

    async def set_house(self, uid: int, house_name: str | None):
        await self.execute("UPDATE users SET house=? WHERE id=?", (house_name, uid))

    async def set_city(self, uid: int, city: str):
        await self.execute("UPDATE users SET city=? WHERE id=?", (city, uid))

    async def set_nickname(self, uid: int, nickname: str):
        now = int(time.time())
        await self.execute(
            "UPDATE users SET nickname=?, last_nick_change=? WHERE id=?",
            (nickname, now, uid),
        )

    async def add_exp(self, uid: int, amount: int):
        user = await self.get_user(uid)
        exp = user["exp"] + amount
        level = user["level"]

        while exp >= 1000:
            exp -= 1000
            level += 1

        await self.execute(
            "UPDATE users SET exp=?, level=? WHERE id=?",
            (exp, level, uid),
        )

    async def set_job_cd(self, uid: int, ts: int):
        await self.execute("UPDATE users SET job_cd=? WHERE id=?", (ts, uid))

    async def use_promo(self, uid: int):
        await self.execute("UPDATE users SET promo_used=1 WHERE id=?", (uid,))

    async def add_inventory_item(self, uid: int, item: dict):
        await self.conn.execute(
            """
            INSERT INTO inventory (user_id, item_type, slot, name, brand, color, price, image_path, equipped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                uid,
                item.get("item_type", "cloth"),
                item["slot"],
                item["name"],
                item.get("brand"),
                item.get("color"),
                item.get("price", 0),
                item.get("image_path"),
            ),
        )
        await self.conn.commit()

    async def get_inventory(self, uid: int):
        return await self.fetchall(
            "SELECT * FROM inventory WHERE user_id=? ORDER BY id DESC",
            (uid,),
        )

    async def get_inventory_item(self, uid: int, item_id: int):
        return await self.fetchone(
            "SELECT * FROM inventory WHERE id=? AND user_id=?",
            (item_id, uid),
        )

    async def equip_item(self, uid: int, item_id: int):
        item = await self.get_inventory_item(uid, item_id)
        if not item:
            return False

        await self.conn.execute(
            "UPDATE inventory SET equipped=0 WHERE user_id=? AND slot=?",
            (uid, item["slot"]),
        )
        await self.conn.execute(
            "UPDATE inventory SET equipped=1 WHERE id=? AND user_id=?",
            (item_id, uid),
        )
        await self.conn.commit()
        return True

    async def get_equipped(self, uid: int):
        rows = await self.fetchall(
            "SELECT * FROM inventory WHERE user_id=? AND equipped=1",
            (uid,),
        )
        result = {"hat": None, "top": None, "pants": None, "shoes": None}
        for row in rows:
            result[row["slot"]] = row
        return result

    async def clear_shop(self):
        await self.execute("DELETE FROM shop_items")

    async def set_shop_items(self, items: list[dict]):
        await self.clear_shop()
        for item in items:
            await self.conn.execute(
                """
                INSERT INTO shop_items (id, item_type, slot, name, brand, color, price, image_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["item_type"],
                    item["slot"],
                    item["name"],
                    item.get("brand"),
                    item.get("color"),
                    item["price"],
                    item.get("image_path"),
                    item["created_at"],
                ),
            )
        await self.conn.commit()

    async def get_shop_items(self, slot: str | None = None):
        if slot:
            return await self.fetchall(
                "SELECT * FROM shop_items WHERE slot=? ORDER BY id DESC",
                (slot,),
            )
        return await self.fetchall("SELECT * FROM shop_items ORDER BY id DESC")

    async def get_shop_item(self, item_id: int):
        return await self.fetchone("SELECT * FROM shop_items WHERE id=?", (item_id,))


db = DB()


# ============================================================
# DATA / CONFIG
# ============================================================
jobs = {
    "courier": {"title": "🚚 Курьер", "reward": 1100, "cd": 120},
    "canteen": {"title": "🍲 Столовая", "reward": 250, "cd": 60},
    "builder": {"title": "🧱 Стройка", "reward": 2500, "cd": 120},
}

houses = {
    "Квартира": 500000,
    "Дом": 5000000,
    "Особняк": 25000000,
}

real_estate_by_city = {
    "Новосёлки": {"Бюджетный дом": 7500000, "Люкс дом": 30000000},
    "Ступино": {"Бюджетная квартира": 500000, "Люкс квартира": 1500000},
    "Кашира": {"Бюджетная квартира": 760000, "Люкс квартира": 1200000},
}

cities = ["Кашира", "Ступино", "Новосёлки"]
city_location_label = {
    "Кашира": "Профиль у Каширы",
    "Ступино": "Профиль у ЦУМа Ступино",
    "Новосёлки": "Профиль у казино Новосёлки",
}

manual_car_fallback = {
    "ВАЗ 2107": {
        "price": 150000,
        "travel_time": 40,
        "description": "Классика АвтоВАЗа, дёшево и просто",
        "image_path": str(CARS_DIR / "vaz.png"),
    },
    "Lada Vesta": {
        "price": 900000,
        "travel_time": 32,
        "description": "Свежая Lada для города",
        "image_path": str(CARS_DIR / "vesta.png"),
    },
    "Toyota Camry": {
        "price": 3200000,
        "travel_time": 25,
        "description": "Надёжный бизнес-седан",
        "image_path": str(CARS_DIR / "camry.png"),
    },
    "BMW M5": {
        "price": 7000000,
        "travel_time": 16,
        "description": "Быстрая и статусная BMW",
        "image_path": str(CARS_DIR / "bmw_m5.png"),
    },
    "Mercedes G63": {
        "price": 25000000,
        "travel_time": 12,
        "description": "Легендарный внедорожник",
        "image_path": str(CARS_DIR / "g63.png"),
    },
    "Porsche 911": {
        "price": 20000000,
        "travel_time": 11,
        "description": "Икона скорости",
        "image_path": str(CARS_DIR / "911.png"),
    },
    "Bugatti Chiron": {
        "price": 120000000,
        "travel_time": 8,
        "description": "Гиперкар",
        "image_path": str(CARS_DIR / "bugatti.png"),
    },
}


# ============================================================
# HELPERS
# ============================================================
def anti_spam(uid: int) -> bool:
    now = time.time()
    if uid in last_msg and now - last_msg[uid] < 1:
        return True
    last_msg[uid] = now
    return False


def human_money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def safe_stem_to_title(stem: str) -> str:
    text = stem.replace("_", " ").replace("-", " ").strip()
    return " ".join(x.capitalize() for x in text.split())


def guess_car_stats(name: str) -> tuple[int, int, str]:
    low = name.lower()

    if "bugatti" in low or "chiron" in low:
        return 120_000_000, 8, "Гиперкар"
    if "ferrari" in low or "lambo" in low or "lamborghini" in low:
        return 30_000_000, 10, "Суперкар"
    if "911" in low or "gtr" in low or "rs7" in low:
        return 18_000_000, 12, "Очень быстрый спорткар"
    if "g63" in low or "gelik" in low:
        return 25_000_000, 12, "Легендарный внедорожник"
    if "bmw" in low or "mercedes" in low or "audi" in low or "porsche" in low:
        return 7_000_000, 18, "Премиум авто"
    if "toyota" in low or "honda" in low or "volkswagen" in low or "hyundai" in low or "kia" in low:
        return 3_000_000, 26, "Надёжный городской автомобиль"
    if "lada" in low or "vaz" in low or "ваз" in low:
        return 150_000, 40, "Классика АвтоВАЗа"

    return 2_000_000, 30, "Автомобиль"


def load_cars() -> dict:
    cars = {}

    if CARS_DIR.exists():
        for file in sorted(CARS_DIR.iterdir()):
            if file.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            name = safe_stem_to_title(file.stem)
            price, travel_time, desc = guess_car_stats(name)
            cars[name] = {
                "price": price,
                "travel_time": travel_time,
                "description": desc,
                "image_path": str(file),
            }

    if not cars:
        cars = manual_car_fallback.copy()

    return cars


cars = load_cars()


def find_city_background(city: str) -> str | None:
    if not CITIES_DIR.exists():
        return None

    variants = [
        f"{city}.jpg",
        f"{city}.png",
        f"{city}.jpeg",
        f"{city}.webp",
        f"{city.lower()}.jpg",
        f"{city.lower()}.png",
    ]

    for name in variants:
        path = CITIES_DIR / name
        if path.exists():
            return str(path)

    # мягкий поиск по части имени
    for file in CITIES_DIR.iterdir():
        if city.lower() in file.stem.lower():
            return str(file)

    return None


def parse_clothes_filename(path: Path, slot: str) -> dict:
    stem = path.stem.replace("-", "_")
    parts = [p for p in stem.split("_") if p]

    brand = parts[0].capitalize() if parts else "Brand"
    color = parts[1].lower() if len(parts) > 1 else "black"
    name = safe_stem_to_title(path.stem)

    if slot == "hat":
        price = random.randint(12_000, 25_000)
    elif slot == "top":
        price = random.randint(25_000, 95_000)
    elif slot == "pants":
        price = random.randint(35_000, 60_000)
    else:
        price = random.randint(60_000, 140_000)

    return {
        "id": random.randint(1000, 999999),
        "item_type": "cloth",
        "slot": slot,
        "name": name,
        "brand": brand,
        "color": color,
        "price": price,
        "image_path": str(path),
        "created_at": int(time.time()),
    }


async def refresh_shop_from_assets():
    items = []
    for slot in ["hat", "top", "pants", "shoes"]:
        slot_dir = CLOTHES_DIR / slot
        slot_candidates = []

        if slot_dir.exists():
            for file in slot_dir.iterdir():
                if file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                    slot_candidates.append(parse_clothes_filename(file, slot))

        random.shuffle(slot_candidates)
        items.extend(slot_candidates[:5])

    if not items:
        # fallback, если картинок одежды нет
        fallback = {
            "hat": [
                {"name": "Кепка New Era", "brand": "New Era", "color": "black", "price": 15000},
                {"name": "Шапка Nike", "brand": "Nike", "color": "white", "price": 12000},
            ],
            "top": [
                {"name": "Худи Nike", "brand": "Nike", "color": "black", "price": 80000},
                {"name": "Куртка Adidas", "brand": "Adidas", "color": "blue", "price": 95000},
                {"name": "Футболка Zara", "brand": "Zara", "color": "white", "price": 25000},
            ],
            "pants": [
                {"name": "Джинсы Levis", "brand": "Levis", "color": "blue", "price": 50000},
                {"name": "Штаны Puma", "brand": "Puma", "color": "black", "price": 42000},
            ],
            "shoes": [
                {"name": "Nike Air Force 1", "brand": "Nike", "color": "white", "price": 120000},
                {"name": "Adidas Superstar", "brand": "Adidas", "color": "white", "price": 85000},
            ],
        }
        for slot, arr in fallback.items():
            for it in arr:
                items.append(
                    {
                        "id": random.randint(1000, 999999),
                        "item_type": "cloth",
                        "slot": slot,
                        "name": it["name"],
                        "brand": it["brand"],
                        "color": it["color"],
                        "price": it["price"],
                        "image_path": None,
                        "created_at": int(time.time()),
                    }
                )

    await db.set_shop_items(items)


def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton(text="💼 Работа", callback_data="jobs")],
            [InlineKeyboardButton(text="🚗 Машины", callback_data="cars")],
            [InlineKeyboardButton(text="🏠 Дома", callback_data="house")],
            [InlineKeyboardButton(text="🏪 ЦУМ", callback_data="tsum")],
            [InlineKeyboardButton(text="🌆 Город", callback_data="city")],
            [InlineKeyboardButton(text="🎁 Промокод", callback_data="promo")],
            [InlineKeyboardButton(text="🤝 Трейд", callback_data="trade")],
            [InlineKeyboardButton(text="🧍 Профиль", callback_data="profile")],
            [InlineKeyboardButton(text="✏️ Ник", callback_data="nickname")],
            [InlineKeyboardButton(text="🛠 Админ", callback_data="admin")],
        ]
    )


def roulette_bet_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Красное x2", callback_data="bet:red"),
                InlineKeyboardButton(text="⚫ Чёрное x2", callback_data="bet:black"),
            ],
            [
                InlineKeyboardButton(text="1-12 x3", callback_data="bet:low"),
                InlineKeyboardButton(text="13-24 x3", callback_data="bet:mid"),
            ],
            [InlineKeyboardButton(text="25-36 x3", callback_data="bet:high")],
            [InlineKeyboardButton(text="🔢 Число x36", callback_data="bet:number")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
        ]
    )


def jobs_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=jobs["courier"]["title"], callback_data="job:courier")],
            [InlineKeyboardButton(text=jobs["canteen"]["title"], callback_data="job:canteen")],
            [InlineKeyboardButton(text=jobs["builder"]["title"], callback_data="job:builder")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
        ]
    )


def city_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=city, callback_data=f"citygo:{city}")] for city in cities
        ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]
    )


def tsum_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧢 Головные уборы", callback_data="tsumcat:hat")],
            [InlineKeyboardButton(text="👕 Верх", callback_data="tsumcat:top")],
            [InlineKeyboardButton(text="👖 Низ", callback_data="tsumcat:pants")],
            [InlineKeyboardButton(text="👟 Обувь", callback_data="tsumcat:shoes")],
            [InlineKeyboardButton(text="📦 Шкаф", callback_data="wardrobe")],
            [InlineKeyboardButton(text="🔄 Обновить ЦУМ", callback_data="refreshshop")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
        ]
    )


def draw_stickman(draw: ImageDraw.ImageDraw):
    # голова
    draw.ellipse((360, 110, 440, 190), fill="white")
    # тело
    draw.line((400, 190, 400, 330), fill="white", width=6)
    # руки
    draw.line((400, 230, 330, 280), fill="white", width=6)
    draw.line((400, 230, 470, 280), fill="white", width=6)
    # ноги
    draw.line((400, 330, 345, 455), fill="white", width=6)
    draw.line((400, 330, 455, 455), fill="white", width=6)


def overlay_clothes(base_img: Image.Image, equipped: dict):
    draw = ImageDraw.Draw(base_img)

    # Если есть реальные PNG с прозрачностью — накладываем.
    # Если нет — рисуем цветные элементы поверх стикмена.

    hat = equipped.get("hat")
    top = equipped.get("top")
    pants = equipped.get("pants")
    shoes = equipped.get("shoes")

    for item, box in [
        (hat, (345, 90, 455, 150)),
        (top, (330, 185, 470, 305)),
        (pants, (350, 305, 450, 430)),
        (shoes, (335, 430, 465, 500)),
    ]:
        if not item:
            continue

        path = item["image_path"]
        if path and os.path.exists(path):
            try:
                cloth = Image.open(path).convert("RGBA")
                cloth = cloth.resize((box[2] - box[0], box[3] - box[1]))
                base_img.alpha_composite(cloth, (box[0], box[1]))
                continue
            except Exception:
                pass

        # fallback: цветной блок + текст
        draw.rounded_rectangle(box, radius=18, outline=(255, 215, 0), width=3, fill=(50, 50, 50, 160))
        draw.text((box[0] + 8, box[1] + 8), item["name"][:14], fill=(255, 255, 0))


def get_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


async def render_profile(uid: int) -> str:
    user = await db.get_user(uid)
    equipped = await db.get_equipped(uid)

    bg_path = find_city_background(user["city"])
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert("RGBA").resize((900, 650))
        except Exception:
            bg = Image.new("RGBA", (900, 650), (50, 50, 50, 255))
    else:
        bg = Image.new("RGBA", (900, 650), (50, 50, 50, 255))

    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # левая инфо-панель
    draw.rounded_rectangle((20, 20, 310, 260), radius=22, fill=(0, 0, 0, 150))
    draw.rounded_rectangle((20, 280, 310, 610), radius=22, fill=(0, 0, 0, 150))

    draw_stickman(draw)
    overlay_clothes(overlay, equipped)

    font_big = get_font(28)
    font_mid = get_font(22)
    font_small = get_font(18)

    draw.text((40, 35), f"🧍 {user['nickname']}", fill=(255, 255, 255), font=font_big)
    draw.text((40, 80), f"💰 Баланс: {human_money(user['balance'])}", fill=(0, 255, 0), font=font_mid)
    draw.text((40, 115), f"⭐ Уровень: {user['level']}", fill=(255, 255, 0), font=font_mid)
    draw.text((40, 150), f"✨ EXP: {user['exp']}/1000", fill=(255, 255, 255), font=font_mid)
    draw.text((40, 185), f"🌆 Город: {user['city']}", fill=(255, 255, 255), font=font_mid)
    draw.text((40, 220), f"🚗 Авто: {user['car'] or 'нет'}", fill=(0, 255, 255), font=font_mid)

    draw.text((40, 300), f"🏠 Дом: {user['house'] or 'нет'}", fill=(255, 255, 255), font=font_mid)
    draw.text((40, 345), "👕 Одежда:", fill=(255, 255, 0), font=font_mid)

    y = 385
    for slot, label in [("hat", "Шапка"), ("top", "Верх"), ("pants", "Низ"), ("shoes", "Обувь")]:
        row = equipped.get(slot)
        text = row["name"] if row else "нет"
        draw.text((40, y), f"• {label}: {text}", fill=(255, 255, 255), font=font_small)
        y += 42

    draw.rounded_rectangle((20, 620, 500, 645), radius=10, fill=(0, 0, 0, 140))
    draw.text((30, 622), city_location_label.get(user["city"], user["city"]), fill=(255, 255, 255), font=font_small)

    result = Image.alpha_composite(bg, overlay).convert("RGB")
    out_path = RENDER_DIR / f"player_{uid}.png"
    result.save(out_path)
    return str(out_path)


# ============================================================
# START / PROFILE / MENU
# ============================================================
@dp.message(Command("start"))
async def start(m: Message):
    uid = m.from_user.id

    if uid in banned and banned[uid] > time.time():
        await m.answer("🚫 Ты забанен")
        return

    ref = None
    args = (m.text or "").split(maxsplit=1)
    if len(args) > 1:
        try:
            ref = int(args[1])
        except Exception:
            ref = None

    await db.ensure_user(uid, ref)
    await m.answer("🎮 Свага Бот", reply_markup=menu())


@dp.callback_query(F.data == "back")
async def back(c: CallbackQuery):
    await c.message.edit_text("🎮 Свага Бот", reply_markup=menu())


@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    await db.ensure_user(c.from_user.id)
    path = await render_profile(c.from_user.id)
    await c.message.answer_photo(FSInputFile(path), caption="🧍 Твой профиль")


# ============================================================
# NICKNAME
# ============================================================
@dp.callback_query(F.data == "nickname")
async def nickname_menu(c: CallbackQuery):
    pending_nickname.add(c.from_user.id)
    await c.message.edit_text("✏️ Напиши новый ник\nНик можно менять раз в 24 часа")


# ============================================================
# PROMO
# ============================================================
@dp.callback_query(F.data == "promo")
async def promo(c: CallbackQuery):
    pending_promo.add(c.from_user.id)
    await c.message.edit_text("🎁 Введи промокод")


# ============================================================
# JOBS
# ============================================================
@dp.callback_query(F.data == "jobs")
async def jobs_handler(c: CallbackQuery):
    await c.message.edit_text("💼 Выбери работу", reply_markup=jobs_menu())


@dp.callback_query(F.data.startswith("job:"))
async def do_job(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)

    key = c.data.split(":", 1)[1]
    if key not in jobs:
        await c.answer("Нет такой работы", show_alert=True)
        return

    job = jobs[key]
    now = int(time.time())
    if now < user["job_cd"]:
        left = user["job_cd"] - now
        await c.answer(f"⏳ Подожди {left} сек", show_alert=True)
        return

    await db.set_job_cd(uid, now + job["cd"])
    await db.add_balance(uid, job["reward"])
    await db.add_exp(uid, 5)

    await c.message.edit_text(
        f"{job['title']}\n💰 Заработал: {human_money(job['reward'])}\n✨ +5 EXP",
        reply_markup=menu(),
    )


# ============================================================
# CITIES
# ============================================================
@dp.callback_query(F.data == "city")
async def city(c: CallbackQuery):
    await c.message.edit_text("🌆 Выбери город", reply_markup=city_menu())


@dp.callback_query(F.data.startswith("citygo:"))
async def move_city_callback(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)
    city = c.data.split(":", 1)[1]

    if city not in cities:
        await c.answer("Город не найден", show_alert=True)
        return

    car_name = user["car"]
    if car_name and car_name in cars:
        travel_time = cars[car_name]["travel_time"]
        transport = f"🚗 {car_name}"
    else:
        travel_time = 60
        transport = "🚕 Такси"

    await c.message.edit_text(f"{transport}\nЕдешь в {city}... {travel_time} сек")
    await asyncio.sleep(2)
    await db.set_city(uid, city)
    await c.message.edit_text(f"✅ Ты приехал в {city}", reply_markup=menu())


# ============================================================
# CARS - AUTOLOAD
# ============================================================
@dp.callback_query(F.data == "cars")
async def cars_menu(c: CallbackQuery):
    global cars
    cars = load_cars()

    rows = []
    for car_name in cars.keys():
        rows.append([InlineKeyboardButton(text=car_name, callback_data=f"viewcar:{car_name}")])
    rows.append([InlineKeyboardButton(text="🔄 Обновить машины", callback_data="reloadcars")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])

    await c.message.edit_text("🚗 Автосалон", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data == "reloadcars")
async def reload_cars(c: CallbackQuery):
    global cars
    cars = load_cars()
    await c.answer("🚗 Машины перезагружены")
    await cars_menu(c)


@dp.callback_query(F.data.startswith("viewcar:"))
async def view_car(c: CallbackQuery):
    name = c.data.split(":", 1)[1]
    car = cars.get(name)
    if not car:
        await c.answer("Машина не найдена", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить", callback_data=f"buycar:{name}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="cars")],
        ]
    )
    caption = (
        f"🚗 {name}\n"
        f"💰 {human_money(car['price'])}\n"
        f"⏱ До города: {car['travel_time']} сек\n"
        f"📄 {car['description']}"
    )

    img = car.get("image_path")
    if img and os.path.exists(img):
        try:
            await c.message.answer_photo(FSInputFile(img), caption=caption, reply_markup=kb)
            return
        except Exception:
            pass

    await c.message.edit_text(caption, reply_markup=kb)


@dp.callback_query(F.data.startswith("buycar:"))
async def buy_car(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)

    name = c.data.split(":", 1)[1]
    car = cars.get(name)
    if not car:
        await c.answer("Машина не найдена", show_alert=True)
        return

    if user["balance"] < car["price"]:
        await c.answer("Нет денег", show_alert=True)
        return

    await db.add_balance(uid, -car["price"])
    await db.set_car(uid, name)
    await c.message.edit_text(f"🚗 Куплено: {name}", reply_markup=menu())


# ============================================================
# HOUSES
# ============================================================
@dp.callback_query(F.data == "house")
async def house_menu(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)

    city = user["city"]
    city_houses = real_estate_by_city.get(city, houses)

    rows = [
        [InlineKeyboardButton(text=f"{name} — {human_money(price)}", callback_data=f"buyhouse:{name}")]
        for name, price in city_houses.items()
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])

    await c.message.edit_text(
        f"🏠 Недвижимость\n📍 Город: {city}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("buyhouse:"))
async def buy_house(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)

    name = c.data.split(":", 1)[1]
    price = real_estate_by_city.get(user["city"], {}).get(name, houses.get(name))
    if not price:
        await c.answer("Дом не найден", show_alert=True)
        return

    if user["balance"] < price:
        await c.answer("Нет денег", show_alert=True)
        return

    await db.add_balance(uid, -price)
    await db.set_house(uid, name)
    await c.message.edit_text(f"🏠 Куплено: {name}", reply_markup=menu())


# ============================================================
# TSUM / SHOP / CLOTHES WITH PREVIEW
# ============================================================
@dp.callback_query(F.data == "tsum")
async def tsum_menu(c: CallbackQuery):
    await c.message.edit_text("🏪 ЦУМ", reply_markup=tsum_menu_keyboard())


@dp.callback_query(F.data == "refreshshop")
async def refresh_shop_handler(c: CallbackQuery):
    await refresh_shop_from_assets()
    await c.answer("🛍 ЦУМ обновлён")
    await c.message.edit_text("🏪 ЦУМ", reply_markup=tsum_menu_keyboard())


@dp.callback_query(F.data.startswith("tsumcat:"))
async def tsum_category(c: CallbackQuery):
    slot = c.data.split(":", 1)[1]
    items = await db.get_shop_items(slot)

    if not items:
        await refresh_shop_from_assets()
        items = await db.get_shop_items(slot)

    rows = []
    for item in items:
        rows.append([
            InlineKeyboardButton(
                text=f"{item['name']} — {human_money(item['price'])}",
                callback_data=f"viewcloth:{item['id']}",
            )
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="tsum")])
    await c.message.edit_text(
        f"🛍 Выбери вещь ({slot})",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@dp.callback_query(F.data.startswith("viewcloth:"))
async def view_cloth(c: CallbackQuery):
    item_id = int(c.data.split(":", 1)[1])
    item = await db.get_shop_item(item_id)
    if not item:
        await c.answer("Вещь не найдена", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить", callback_data=f"buycloth:{item['id']}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"tsumcat:{item['slot']}")],
        ]
    )

    caption = (
        f"🛍 {item['name']}\n"
        f"🏷 Бренд: {item['brand'] or '-'}\n"
        f"🎨 Цвет: {item['color'] or '-'}\n"
        f"👕 Слот: {item['slot']}\n"
        f"💰 Цена: {human_money(item['price'])}"
    )

    img = item["image_path"]
    if img and os.path.exists(img):
        try:
            await c.message.answer_photo(FSInputFile(img), caption=caption, reply_markup=kb)
            return
        except Exception:
            pass

    await c.message.edit_text(caption, reply_markup=kb)


@dp.callback_query(F.data.startswith("buycloth:"))
async def buy_cloth(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)

    item_id = int(c.data.split(":", 1)[1])
    item = await db.get_shop_item(item_id)
    if not item:
        await c.answer("Вещь не найдена", show_alert=True)
        return

    if user["balance"] < item["price"]:
        await c.answer("Нет денег", show_alert=True)
        return

    await db.add_balance(uid, -item["price"])
    await db.add_inventory_item(
        uid,
        {
            "item_type": item["item_type"],
            "slot": item["slot"],
            "name": item["name"],
            "brand": item["brand"],
            "color": item["color"],
            "price": item["price"],
            "image_path": item["image_path"],
        },
    )
    await c.message.edit_text(f"✅ Куплено: {item['name']}", reply_markup=menu())


@dp.callback_query(F.data == "wardrobe")
async def wardrobe(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    items = await db.get_inventory(uid)

    rows = []
    if not items:
        rows.append([InlineKeyboardButton(text="Шкаф пуст", callback_data="noop")])
    else:
        for item in items[:40]:
            equipped_mark = "✅ " if item["equipped"] else ""
            rows.append([
                InlineKeyboardButton(
                    text=f"{equipped_mark}{item['name']}",
                    callback_data=f"wearitem:{item['id']}",
                )
            ])

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="tsum")])
    await c.message.edit_text("📦 Шкаф", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("wearitem:"))
async def wear_inventory_item(c: CallbackQuery):
    uid = c.from_user.id
    item_id = int(c.data.split(":", 1)[1])

    ok = await db.equip_item(uid, item_id)
    if not ok:
        await c.answer("Вещь не найдена", show_alert=True)
        return

    item = await db.get_inventory_item(uid, item_id)
    await c.message.edit_text(f"👕 Надето: {item['name']}", reply_markup=menu())


@dp.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


# ============================================================
# CASINO / ROULETTE / DICE
# ============================================================
@dp.callback_query(F.data == "casino")
async def casino(c: CallbackQuery):
    await c.message.edit_text("🎰 Рулетка — выбери ставку", reply_markup=roulette_bet_menu())


@dp.callback_query(F.data == "bet:number")
async def roulette_number_prompt(c: CallbackQuery):
    pending_number_bet[c.from_user.id] = True
    await c.message.edit_text("🔢 Напиши число от 0 до 36")


@dp.callback_query(F.data.startswith("bet:"))
async def bet(c: CallbackQuery):
    uid = c.from_user.id
    await db.ensure_user(uid)
    user = await db.get_user(uid)

    mode = c.data.split(":", 1)[1]
    if mode == "number":
        return

    bet_amount = 1000
    if user["balance"] < bet_amount:
        await c.answer("Нет денег", show_alert=True)
        return

    num = random.randint(0, 36)
    win = 0

    if mode == "red" and num in red_numbers:
        win = bet_amount * 2
    elif mode == "black" and num in black_numbers:
        win = bet_amount * 2
    elif mode == "low" and 1 <= num <= 12:
        win = bet_amount * 3
    elif mode == "mid" and 13 <= num <= 24:
        win = bet_amount * 3
    elif mode == "high" and 25 <= num <= 36:
        win = bet_amount * 3

    await db.add_balance(uid, -bet_amount)
    if win:
        await db.add_balance(uid, win)

    updated = await db.get_user(uid)
    color = "зелёное" if num == 0 else ("красное" if num in red_numbers else "чёрное")
    result = "🎉 Выигрыш" if win else "💀 Проигрыш"

    await c.message.answer(
        f"🎯 Выпало {num} ({color})\n"
        f"{result}\n"
        f"Баланс: {human_money(updated['balance'])}"
    )


@dp.message(F.text == "кости")
async def dice(m: Message):
    p1 = random.randint(1, 6)
    p2 = random.randint(1, 6)
    if p1 > p2:
        res = "Ты выиграл"
    elif p1 < p2:
        res = "Ты проиграл"
    else:
        res = "Ничья"
    await m.answer(f"🎲 {p1} vs {p2}\n{res}")


# ============================================================
# TRADE
# ============================================================
@dp.callback_query(F.data == "trade")
async def trade(c: CallbackQuery):
    await c.message.edit_text("🤝 Напиши: trade user_id")


# ============================================================
# ADMIN
# ============================================================
@dp.callback_query(F.data == "admin")
async def admin(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS:
        await c.answer("Нет доступа", show_alert=True)
        return
    await c.message.edit_text("/ban id дни | /unban id | /add id сумма", reply_markup=menu())


@dp.message(Command("ban"))
async def ban(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid, days = m.text.split()
        banned[int(uid)] = time.time() + int(days) * 86400
        await m.answer("Забанен")
    except Exception:
        await m.answer("Используй: /ban id дни")


@dp.message(Command("unban"))
async def unban(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid = m.text.split()
        banned.pop(int(uid), None)
        await m.answer("Разбан")
    except Exception:
        await m.answer("Используй: /unban id")


@dp.message(Command("add"))
async def add(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        _, uid, amt = m.text.split()
        await db.ensure_user(int(uid))
        await db.add_balance(int(uid), int(amt))
        await m.answer("Выдано")
    except Exception:
        await m.answer("Используй: /add id сумма")


# ============================================================
# UNIVERSAL MESSAGE HANDLER
# ============================================================
@dp.message()
async def handle_text(m: Message):
    uid = m.from_user.id

    if anti_spam(uid):
        return

    if uid in banned and banned[uid] > time.time():
        await m.answer("🚫 Ты забанен")
        return

    await db.ensure_user(uid)
    text = (m.text or "").strip()
    user = await db.get_user(uid)

    # number roulette
    if pending_number_bet.get(uid):
        pending_number_bet.pop(uid, None)
        bet_amount = 1000
        if user["balance"] < bet_amount:
            await m.answer("Нет денег")
            return

        try:
            chosen = int(text)
        except Exception:
            await m.answer("Нужно число от 0 до 36")
            return

        if not 0 <= chosen <= 36:
            await m.answer("Нужно число от 0 до 36")
            return

        num = random.randint(0, 36)
        win = bet_amount * 36 if num == chosen else 0

        await db.add_balance(uid, -bet_amount)
        if win:
            await db.add_balance(uid, win)

        updated = await db.get_user(uid)
        result = "🎉 Выигрыш" if win else "💀 Проигрыш"
        await m.answer(
            f"🎯 Выпало {num}\n"
            f"Твоё число: {chosen}\n"
            f"{result}\n"
            f"Баланс: {human_money(updated['balance'])}"
        )
        return

    # promo
    if uid in pending_promo:
        pending_promo.remove(uid)
        if text != PROMO_CODE:
            await m.answer("❌ Неверный промокод", reply_markup=menu())
            return
        if user["promo_used"]:
            await m.answer("❌ Уже использован", reply_markup=menu())
            return
        await db.add_balance(uid, PROMO_REWARD)
        await db.use_promo(uid)
        await m.answer(f"🎁 Получено {human_money(PROMO_REWARD)}", reply_markup=menu())
        return

    # nickname
    if uid in pending_nickname:
        pending_nickname.remove(uid)
        now = int(time.time())
        if now - user["last_nick_change"] < 86400:
            left = 86400 - (now - user["last_nick_change"])
            hours = max(1, left // 3600)
            await m.answer(f"❌ Ник можно менять раз в 24 часа. Осталось ~{hours} ч.", reply_markup=menu())
            return
        if len(text) < 2 or len(text) > 20:
            await m.answer("❌ Ник должен быть от 2 до 20 символов", reply_markup=menu())
            return
        await db.set_nickname(uid, text)
        await m.answer(f"✅ Новый ник: {text}", reply_markup=menu())
        return

    # trade request
    if text.startswith("trade "):
        try:
            target_id = int(text.split()[1])
        except Exception:
            await m.answer("Используй: trade user_id")
            return

        if target_id == uid:
            await m.answer("❌ Нельзя трейдиться с собой")
            return

        pending_trade[target_id] = uid
        await db.ensure_user(target_id)
        await m.answer("🤝 Запрос отправлен. Второй игрок должен написать: accept")
        return

    if text.lower() == "accept":
        if uid not in pending_trade:
            await m.answer("❌ Нет активного запроса")
            return

        other = pending_trade.pop(uid)
        my_items = await db.fetchall(
            "SELECT * FROM inventory WHERE user_id=? AND equipped=1 LIMIT 1",
            (uid,),
        )
        other_items = await db.fetchall(
            "SELECT * FROM inventory WHERE user_id=? AND equipped=1 LIMIT 1",
            (other,),
        )

        if not my_items or not other_items:
            await m.answer("❌ Для простого трейда у обоих должна быть хотя бы 1 надетая вещь")
            return

        my_item = my_items[0]
        other_item = other_items[0]

        await db.execute("UPDATE inventory SET user_id=?, equipped=0 WHERE id=?", (other, my_item["id"]))
        await db.execute("UPDATE inventory SET user_id=?, equipped=0 WHERE id=?", (uid, other_item["id"]))
        await m.answer("✅ Обмен завершён")
        return

    # referral help
    if text.lower() == "ref":
        await m.answer(f"🔗 Твоя рефералка: /start {uid}")
        return

    # support
    if text.lower() == "support":
        await m.answer("📞 Напишите менеджеру: @pipikaka3322")
        return


# ============================================================
# MAIN
# ============================================================
async def main():
    await db.connect()
    await refresh_shop_from_assets()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
