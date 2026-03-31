# 🚀 СВАГА БОТ — FINAL PRO 6.0 (ТРЕЙД + ОДЕЖДА PNG + ПЕРЕЕЗД 60 СЕК)

import asyncio
import random
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from PIL import Image, ImageDraw

BOT_TOKEN = "YOUR_TOKEN"
ADMIN_IDS = {8039924340}

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

BASE = Path(**file**).resolve().parent
ASSETS = BASE / "assets"
CLOTHES = ASSETS / "clothes"
BG = ASSETS / "backgrounds"
GEN = BASE / "generated"

for p in [CLOTHES, BG, GEN]:
p.mkdir(parents=True, exist_ok=True)

users = {}
trades = {}

# ===== USER =====

def get_user(uid):
if uid not in users:
users[uid] = {
"balance": 5000,
"city": "Кашира",
"inventory": [],
"equipped": {"hat": None, "top": None, "pants": None, "shoes": None}
}
return users[uid]

# ===== ГОРОДА =====

cities = ["Кашира","Ступино","Новосёлки"]

@dp.callback_query(F.data == "city")
async def city(c):
kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x, callback_data=f"go:{x}")] for x in cities])
await c.message.edit_text("🌆 Куда ехать?", reply_markup=kb)

@dp.callback_query(F.data.startswith("go:"))
async def go(c):
user = get_user(c.from_user.id)
city = c.data.split(":")[1]

```
await c.message.edit_text(f"🚕 Едешь в {city}... 60 сек")
await asyncio.sleep(60)

user["city"] = city
await c.message.edit_text(f"✅ Ты приехал в {city}", reply_markup=menu())
```

# ===== ЦУМ =====

def gen_item():
cat = random.choice(["hat","top","pants","shoes"])
path = CLOTHES / f"{cat}.png"
if not path.exists():
img = Image.new("RGBA", (200,200),(0,0,0,0))
d = ImageDraw.Draw(img)
d.rectangle([50,50,150,150], fill=(255,255,255))
img.save(path)
return {"id":random.randint(1000,9999),"cat":cat,"img":path}

shop = [gen_item() for _ in range(10)]

@dp.callback_query(F.data == "tsum")
async def tsum(c):
kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{i['cat']} {i['id']}", callback_data=f"buy:{i['id']}")] for i in shop])
await c.message.edit_text("🛍 ЦУМ", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy:"))
async def buy(c):
uid = c.from_user.id
u = get_user(uid)
iid = int(c.data.split(":")[1])
for i in shop:
if i["id"] == iid:
u["inventory"].append(i)
await c.message.answer_photo(FSInputFile(i["img"]), caption="Куплено")

# ===== ТРЕЙД =====

@dp.message(Command("trade"))
async def trade_start(m):
_, uid = m.text.split()
trades[m.from_user.id] = int(uid)
await m.answer("📦 Трейд отправлен")

@dp.message(Command("give"))
async def give(m):
user = get_user(m.from_user.id)
if m.from_user.id not in trades:
return
target = trades[m.from_user.id]
if not user["inventory"]:
return
item = user["inventory"].pop()
get_user(target)["inventory"].append(item)
await m.answer("✅ Передано")

# ===== РЕНДЕР (ОДЕЖДА PNG) =====

def render(uid):
u = get_user(uid)

```
img = Image.new("RGBA", (500,500),(0,0,0,0))
d = ImageDraw.Draw(img)

# тело
d.ellipse((220,50,280,110), fill="white")
d.line((250,110,250,250), fill="white", width=5)

# одежда наложение
for item in u["inventory"]:
    try:
        cloth = Image.open(item["img"]).convert("RGBA")
        img.alpha_composite(cloth.resize((200,200)), (150,100))
    except:
        pass

path = GEN / f"player_{uid}.png"
img.save(path)
return path
```

@dp.callback_query(F.data == "profile")
async def profile(c):
p = render(c.from_user.id)
await c.message.answer_photo(FSInputFile(p))

# ===== UI =====

def menu():
return InlineKeyboardMarkup(inline_keyboard=[
[InlineKeyboardButton(text="🏪 ЦУМ", callback_data="tsum")],
[InlineKeyboardButton(text="🌆 Город", callback_data="city")],
[InlineKeyboardButton(text="🧍 Профиль", callback_data="profile")],
])

@dp.message(Command("start"))
async def start(m):
get_user(m.from_user.id)
await m.answer("🚀 Бот", reply_markup=menu())

# ===== RUN =====

async def main():
await dp.start_polling(bot)

if **name** == "**main**":
asyncio.run(main())
