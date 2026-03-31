import asyncio
import os
import random
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from PIL import Image, ImageDraw

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip().isdigit()
}

if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в переменных окружения")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

users: dict[int, dict] = {}
banned: dict[int, float] = {}
last_msg: dict[int, float] = {}
pending_number_bet: dict[int, bool] = {}

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CARS_DIR = ASSETS_DIR / "cars"
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

city_backgrounds = {
    "Кашира": ASSETS_DIR / "backgrounds" / "kashira.jpg",
    "Ступино": ASSETS_DIR / "backgrounds" / "stupino.jpg",
    "Новосёлки": ASSETS_DIR / "backgrounds" / "novoselki.jpg",
}

cars = {
    "ВАЗ": (100000, 40, "Классика АвтоВАЗа, дёшево и просто", CARS_DIR / "vaz.png"),
    "BMW": (5000000, 20, "Немецкий комфорт и динамика", CARS_DIR / "bmw.png"),
    "Lambo": (40000000, 10, "Суперкар, очень быстрый", CARS_DIR / "lambo.png"),
    "Toyota Camry": (3200000, 25, "Надёжный бизнес-седан", CARS_DIR / "camry.png"),
    "Toyota Land Cruiser": (9000000, 18, "Внедорожник премиум-класса", CARS_DIR / "lc.png"),
    "Honda Civic": (2500000, 30, "Экономичный городской авто", CARS_DIR / "civic.png"),
    "Honda Accord": (3000000, 25, "Комфорт и стиль", CARS_DIR / "accord.png"),
    "Mercedes C-Class": (5500000, 20, "Премиум седан", CARS_DIR / "cclass.png"),
    "Mercedes E-Class": (7000000, 18, "Бизнес-класс", CARS_DIR / "eclass.png"),
    "Mercedes G63": (25000000, 12, "Легендарный внедорожник", CARS_DIR / "g63.png"),
    "BMW X5": (8500000, 15, "Комфортный кроссовер", CARS_DIR / "x5.png"),
    "BMW X6": (11000000, 14, "Спортивный SUV", CARS_DIR / "x6.png"),
    "Audi A6": (6000000, 20, "Технологичный седан", CARS_DIR / "a6.png"),
    "Audi Q7": (9000000, 16, "Семейный кроссовер", CARS_DIR / "q7.png"),
    "Audi RS7": (15000000, 12, "Очень быстрый спорт-седан", CARS_DIR / "rs7.png"),
    "Volkswagen Passat": (2800000, 30, "Практичный авто", CARS_DIR / "passat.png"),
    "Volkswagen Touareg": (7500000, 18, "Комфортный внедорожник", CARS_DIR / "touareg.png"),
    "Kia K5": (2600000, 28, "Современный седан", CARS_DIR / "k5.png"),
    "Hyundai Sonata": (2400000, 30, "Надёжный и доступный", CARS_DIR / "sonata.png"),
    "Hyundai Tucson": (3500000, 25, "Городской кроссовер", CARS_DIR / "tucson.png"),
    "Nissan GT-R": (18000000, 12, "Легендарный спорткар", CARS_DIR / "gtr.png"),
    "Porsche Cayenne": (12000000, 14, "Премиум SUV", CARS_DIR / "cayenne.png"),
    "Porsche 911": (20000000, 11, "Икона скорости", CARS_DIR / "911.png"),
    "Ferrari 488": (30000000, 10, "Суперкар Ferrari", CARS_DIR / "ferrari.png"),
    "Bugatti Chiron": (120000000, 8, "Гиперкар", CARS_DIR / "bugatti.png"),
}

houses = {"Квартира": 500000, "Дом": 5000000}

clothing_shop = {
    "hat": [
        {"name": "Кепка New Era", "price": 15000},
        {"name": "Шапка Nike", "price": 12000},
    ],
    "top": [
        {"name": "Худи Nike", "price": 80000},
        {"name": "Куртка Adidas", "price": 95000},
        {"name": "Футболка Zara", "price": 25000},
    ],
    "pants": [
        {"name": "Джинсы Levis", "price": 50000},
        {"name": "Штаны Puma", "price": 42000},
    ],
    "shoes": [
        {"name": "Nike Air Force 1", "price": 120000},
        {"name": "Adidas Superstar", "price": 85000},
    ],
}

red_numbers = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
black_numbers = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
cities = ["Кашира", "Ступино", "Новосёлки"]


def get_user(uid: int) -> dict:
    if uid not in users:
        users[uid] = {
            "balance": 5000,
            "car": None,
            "house": None,
            "city": "Кашира",
            "clothes": {"hat": None, "top": None, "pants": None, "shoes": None},
            "inventory": [],
        }
    return users[uid]


def anti_spam(uid: int) -> bool:
    now = time.time()
    if uid in last_msg and now - last_msg[uid] < 1:
        return True
    last_msg[uid] = now
    return False


def is_banned(uid: int) -> bool:
    until = banned.get(uid)
    return bool(until and until > time.time())


def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Казино", callback_data="casino")],
            [InlineKeyboardButton(text="🚗 Машины", callback_data="cars")],
            [InlineKeyboardButton(text="🏠 Дома", callback_data="house")],
            [InlineKeyboardButton(text="🏪 ЦУМ", callback_data="tsum")],
            [InlineKeyboardButton(text="🌆 Город", callback_data="city")],
            [InlineKeyboardButton(text="🧍 Профиль", callback_data="profile")],
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


def generate_placeholder_car_image(name: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 500), (28, 28, 28))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((120, 180, 780, 360), radius=25, outline="white", width=4)
    d.rounded_rectangle((250, 120, 650, 230), radius=20, outline="white", width=4)
    d.ellipse((180, 330, 300, 450), outline="white", width=6)
    d.ellipse((600, 330, 720, 450), outline="white", width=6)
    d.text((40, 40), name, fill="white")
    d.text((40, 80), "placeholder image", fill=(180, 180, 180))
    img.save(path)


def ensure_assets() -> None:
    (ASSETS_DIR / "backgrounds").mkdir(parents=True, exist_ok=True)
    for city, path in city_backgrounds.items():
        if not path.exists():
            img = Image.new("RGB", (1280, 720), (60, 60, 60))
            d = ImageDraw.Draw(img)
            d.text((40, 40), city, fill="white")
            d.text((40, 90), "Добавь реальный фон в assets/backgrounds", fill=(220, 220, 220))
            img.save(path)
    for _, (_, _, _, path) in cars.items():
        if not path.exists():
            generate_placeholder_car_image(path.stem, path)


def render(uid: int) -> Path:
    u = get_user(uid)
    bg_path = city_backgrounds.get(u["city"])
    try:
        img = Image.open(bg_path).convert("RGB").resize((800, 600))
    except Exception:
        img = Image.new("RGB", (800, 600), (50, 50, 50))

    d = ImageDraw.Draw(img)

    # stickman
    d.ellipse((360, 120, 420, 180), fill="white")
    d.line((390, 180, 390, 320), fill="white", width=4)
    d.line((390, 220, 330, 270), fill="white", width=4)
    d.line((390, 220, 450, 270), fill="white", width=4)
    d.line((390, 320, 340, 420), fill="white", width=4)
    d.line((390, 320, 440, 420), fill="white", width=4)

    d.text((20, 20), f"Город: {u['city']}", fill=(255, 255, 255))
    d.text((20, 50), f"Авто: {u['car']}", fill=(0, 255, 0))
    d.text((20, 80), f"Дом: {u['house']}", fill=(0, 255, 255))

    y = 120
    for slot, value in u["clothes"].items():
        if value:
            d.text((20, y), f"{slot}: {value}", fill=(255, 255, 0))
            y += 28

    location_label = {
        "Кашира": "Профиль у Каширы",
        "Ступино": "Профиль у ЦУМа Ступино",
        "Новосёлки": "Профиль у казино Новосёлки",
    }
    d.text((20, 540), location_label.get(u["city"], u["city"]), fill=(255, 255, 255))

    path = GENERATED_DIR / f"player_{uid}.png"
    img.save(path)
    return path


@dp.message(Command("start"))
async def start(m: Message):
    uid = m.from_user.id
    if is_banned(uid):
        await m.answer("🚫 Ты забанен")
        return
    get_user(uid)
    await m.answer("🎮 Свага Бот", reply_markup=menu())


@dp.callback_query(F.data == "city")
async def city(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=x, callback_data=f"citygo:{x}")] for x in cities
    ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]])
    await c.message.edit_text("🌆 Выбери город", reply_markup=kb)


@dp.callback_query(F.data.startswith("citygo:"))
async def move_city(c: CallbackQuery):
    user = get_user(c.from_user.id)
    city_name = c.data.split(":", 1)[1]

    if user["car"] and user["car"] in cars:
        travel_time = cars[user["car"]][1]
        transport = f"🚗 {user['car']}"
    else:
        travel_time = 60
        transport = "🚕 Такси"

    await c.message.edit_text(f"{transport}\nЕдешь в {city_name}... {travel_time} сек")
    await asyncio.sleep(2)
    user["city"] = city_name
    await c.message.edit_text(f"✅ Ты приехал в {city_name}", reply_markup=menu())


@dp.callback_query(F.data == "cars")
async def cars_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=k, callback_data=f"viewcar:{k}")] for k in cars]
        + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]
    )
    await c.message.edit_text("🚗 Автосалон", reply_markup=kb)


@dp.callback_query(F.data.startswith("viewcar:"))
async def view_car(c: CallbackQuery):
    name = c.data.split(":", 1)[1]
    price, speed, desc, img = cars[name]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Купить", callback_data=f"buycar:{name}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cars")],
    ])
    caption = f"{name}\n💰 {price}\n⏱ До города: {speed} сек\n📄 {desc}"
    try:
        await c.message.answer_photo(FSInputFile(img), caption=caption, reply_markup=kb)
    except Exception:
        await c.message.edit_text(caption, reply_markup=kb)


@dp.callback_query(F.data.startswith("buycar:"))
async def buy_car(c: CallbackQuery):
    name = c.data.split(":", 1)[1]
    price, _, _, _ = cars[name]
    user = get_user(c.from_user.id)
    if user["balance"] < price:
        await c.answer("Нет денег", show_alert=True)
        return
    user["balance"] -= price
    user["car"] = name
    await c.message.edit_text(f"🚗 Куплено: {name}", reply_markup=menu())


@dp.callback_query(F.data == "house")
async def house_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{k} {v}", callback_data=f"buyhouse:{k}")]
            for k, v in houses.items()
        ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]
    )
    await c.message.edit_text("🏠 Недвижимость", reply_markup=kb)


@dp.callback_query(F.data.startswith("buyhouse:"))
async def buy_house(c: CallbackQuery):
    name = c.data.split(":", 1)[1]
    user = get_user(c.from_user.id)
    if user["balance"] < houses[name]:
        await c.answer("Нет денег", show_alert=True)
        return
    user["balance"] -= houses[name]
    user["house"] = name
    await c.message.edit_text(f"🏠 Куплено: {name}", reply_markup=menu())


@dp.callback_query(F.data == "tsum")
async def tsum_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧢 Головные уборы", callback_data="tsumcat:hat")],
        [InlineKeyboardButton(text="👕 Верх", callback_data="tsumcat:top")],
        [InlineKeyboardButton(text="👖 Низ", callback_data="tsumcat:pants")],
        [InlineKeyboardButton(text="👟 Обувь", callback_data="tsumcat:shoes")],
        [InlineKeyboardButton(text="📦 Шкаф", callback_data="wardrobe")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")],
    ])
    await c.message.edit_text("🏪 ЦУМ", reply_markup=kb)


@dp.callback_query(F.data.startswith("tsumcat:"))
async def tsum_category(c: CallbackQuery):
    category = c.data.split(":", 1)[1]
    rows = []
    for i, item in enumerate(clothing_shop[category]):
        rows.append([
            InlineKeyboardButton(
                text=f"{item['name']} — {item['price']}",
                callback_data=f"buycloth:{category}:{i}",
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="tsum")])
    await c.message.edit_text("Выбери вещь", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("buycloth:"))
async def buy_cloth(c: CallbackQuery):
    _, category, idx = c.data.split(":")
    item = clothing_shop[category][int(idx)]
    user = get_user(c.from_user.id)
    if user["balance"] < item["price"]:
        await c.answer("Нет денег", show_alert=True)
        return
    user["balance"] -= item["price"]
    user["inventory"].append({"slot": category, "name": item["name"]})
    await c.message.edit_text(f"✅ Куплено: {item['name']}", reply_markup=menu())


@dp.callback_query(F.data == "wardrobe")
async def wardrobe(c: CallbackQuery):
    user = get_user(c.from_user.id)
    rows = []
    for i, item in enumerate(user["inventory"]):
        rows.append([InlineKeyboardButton(text=f"Надеть: {item['name']}", callback_data=f"wearidx:{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="tsum")])
    await c.message.edit_text("📦 Шкаф", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("wearidx:"))
async def wear_inventory_item(c: CallbackQuery):
    idx = int(c.data.split(":", 1)[1])
    user = get_user(c.from_user.id)
    if idx < 0 or idx >= len(user["inventory"]):
        await c.answer("Вещь не найдена", show_alert=True)
        return
    item = user["inventory"][idx]
    user["clothes"][item["slot"]] = item["name"]
    await c.message.edit_text(f"👕 Надето: {item['name']}", reply_markup=menu())


@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    path = render(c.from_user.id)
    await c.message.answer_photo(FSInputFile(path), caption="🧍 Твой профиль")


@dp.callback_query(F.data == "casino")
async def casino(c: CallbackQuery):
    await c.message.edit_text("🎰 Рулетка — выбери ставку", reply_markup=roulette_bet_menu())


@dp.callback_query(F.data == "bet:number")
async def roulette_number_prompt(c: CallbackQuery):
    pending_number_bet[c.from_user.id] = True
    await c.message.edit_text("Напиши число от 0 до 36")


@dp.callback_query(F.data.startswith("bet:"))
async def bet(c: CallbackQuery):
    uid = c.from_user.id
    user = get_user(uid)
    bet_amount = 1000
    if user["balance"] < bet_amount:
        await c.answer("Нет денег", show_alert=True)
        return

    user["balance"] -= bet_amount
    mode = c.data.split(":", 1)[1]
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

    user["balance"] += win
    color = "зелёное" if num == 0 else ("красное" if num in red_numbers else "чёрное")
    result = "🎉 Выигрыш" if win else "💀 Проигрыш"
    await c.message.answer(f"🎯 Выпало {num} ({color})\n{result}\nБаланс: {user['balance']}")


@dp.message()
async def handle_number_bet(m: Message):
    uid = m.from_user.id
    if anti_spam(uid):
        return
    if is_banned(uid):
        await m.answer("🚫 Ты забанен")
        return
    if pending_number_bet.get(uid):
        pending_number_bet.pop(uid, None)
        user = get_user(uid)
        bet_amount = 1000
        if user["balance"] < bet_amount:
            await m.answer("Нет денег")
            return
        try:
            chosen = int((m.text or "").strip())
        except Exception:
            await m.answer("Нужно число от 0 до 36")
            return
        if not 0 <= chosen <= 36:
            await m.answer("Нужно число от 0 до 36")
            return
        user["balance"] -= bet_amount
        num = random.randint(0, 36)
        win = bet_amount * 36 if num == chosen else 0
        user["balance"] += win
        result = "🎉 Выигрыш" if win else "💀 Проигрыш"
        await m.answer(f"🎯 Выпало {num}\nТвоё число: {chosen}\n{result}\nБаланс: {user['balance']}")
        return


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
    _, uid, days = m.text.split()
    banned[int(uid)] = time.time() + int(days) * 86400
    await m.answer("Забанен")


@dp.message(Command("unban"))
async def unban(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    _, uid = m.text.split()
    banned.pop(int(uid), None)
    await m.answer("Разбан")


@dp.message(Command("add"))
async def add(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    _, uid, amt = m.text.split()
    get_user(int(uid))["balance"] += int(amt)
    await m.answer("Выдано")


@dp.callback_query(F.data == "back")
async def back(c: CallbackQuery):
    await c.message.edit_text("🎮 Свага Бот", reply_markup=menu())


async def main():
    ensure_assets()
    print("BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
