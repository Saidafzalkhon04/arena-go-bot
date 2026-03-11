import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from aiohttp import web
from datetime import datetime

from db import Database

# Logging sozlamalari
logging.basicConfig(level=logging.INFO )

# Bot tokeni
TOKEN = "8724037162:AAHoxj_-NSO96BnoL7O85WlPDiBYSmQFqUU"

# Ma'lumotlar bazasi
db = Database("arena_go.db")

# Bot va Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Render Port Fix (Render xatoligini oldini olish uchun) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- FSM Holatlari ---
class Reg(StatesGroup):
    role = State()

class AddSt(StatesGroup):
    name = State()
    link = State()
    loc = State()
    price = State()
    hours = State()
    photo = State()

class Book(StatesGroup):
    sid = State()
    date = State()
    slot = State()

# --- Klaviaturalar ---
def main_menu(is_owner=False):
    kb = []
    if is_owner:
        kb.append([KeyboardButton(text="Mening Stadionlarim"), KeyboardButton(text="Stadion Qo'shish")])
    else:
        kb.append([KeyboardButton(text="Yaqin Stadionlar", request_location=True), KeyboardButton(text="Barcha Stadionlar")])
        kb.append([KeyboardButton(text="Jamoa 🤝"), KeyboardButton(text="Mening Bronlarim")])
    kb.append([KeyboardButton(text="Profil")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Handlerlar ---
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Mijoz"), KeyboardButton(text="Stadion Egasi")]], resize_keyboard=True)
    await message.answer("Xush kelibsiz! Iltimos, rolingizni tanlang:", reply_markup=kb)
    await state.set_state(Reg.role)

@dp.message(Reg.role)
async def set_role(message: types.Message, state: FSMContext):
    is_owner = 1 if message.text == "Stadion Egasi" else 0
    db.update_user_role(message.from_user.id, is_owner)
    await message.answer(f"Siz {message.text} sifatida ro'yxatdan o'tdingiz.", reply_markup=main_menu(is_owner))
    await state.clear()

# --- Stadionlar ro'yxati va Yaqin stadionlar ---
@dp.message(F.text == "Barcha Stadionlar")
@dp.message(F.location)
async def list_stadiums(message: types.Message):
    stadiums = db.get_all_stadiums()
    u_loc = (message.location.latitude, message.location.longitude) if message.location else None
    
    if message.location:
        await message.answer("📍 Sizga yaqin (5 km radiusdagi) stadionlar qidirilmoqda...")
    
    found = False
    for s in stadiums:
        dist = None
        if u_loc:
            dist = geodesic(u_loc, (s[4], s[5])).km
            if dist > 5: continue # 5 km dan uzoq bo'lsa o'tkazib yuboramiz
        
        found = True
        dist_text = f"📏 Masofa: {dist:.2f} km\n" if dist else ""
        text = f"🏟 **{s[2]}**\n{dist_text}💰 Narxi: {s[6]:,} so'm\n⏰ Ish vaqti: {s[7]}\n📍 [Google Maps Link]({s[3]})"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bron qilish 📅", callback_data=f"book_{s[0]}") ]])
        await message.answer_photo(s[8], caption=text, reply_markup=kb, parse_mode="Markdown")
    
    if not found:
        await message.answer("Hozircha stadionlar topilmadi yoki 5 km radiusda stadion yo'q.")

# --- Bron qilish jarayoni (Vaqtlar bilan) ---
@dp.callback_query(F.data.startswith("book_"))
async def start_booking(cb: types.CallbackQuery, state: FSMContext):
    s_id = int(cb.data.split("_")[1])
    await state.update_data(sid=s_id)
    await cb.message.answer("Bron qilish sanasini kiriting (masalan: 2024-03-11):")
    await state.set_state(Book.date)
    await cb.answer()

@dp.message(Book.date)
async def process_date(message: types.Message, state: FSMContext):
    data = await state.get_data()
    s = db.get_stadium_by_id(data['sid'])
    booked_slots = db.get_booked_slots(data['sid'], message.text)
    
    # Ish vaqtini tahlil qilish (format: 09:00-22:00)
    try:
        times = s[7].split("-")
        start_h = int(times[0].split(":")[0])
        end_h = int(times[1].split(":")[0])
    except:
        start_h, end_h = 9, 22 # Xato bo'lsa standart vaqt
    
    kb_list = []
    for h in range(start_h, end_h):
        slot = f"{h:02d}:00-{(h+1):02d}:00"
        if slot not in booked_slots:
            kb_list.append([InlineKeyboardButton(text=slot, callback_data=f"slot_{slot}")])
    
    if not kb_list:
        await message.answer("Ushbu kunda barcha vaqtlar band yoki ish vaqti tugagan.")
        await state.clear()
        return

    await state.update_data(date=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await message.answer(f"🏟 {s[2]}\n📅 Sana: {message.text}\n\nBo'sh vaqtni tanlang:", reply_markup=kb)
    await state.set_state(Book.slot)

@dp.callback_query(F.data.startswith("slot_"))
async def process_slot(cb: types.CallbackQuery, state: FSMContext):
    slot = cb.data.split("_")[1]
    data = await state.get_data()
    db.add_booking(cb.from_user.id, data['sid'], data['date'], slot)
    await cb.message.edit_text(f"✅ Bron muvaffaqiyatli amalga oshirildi!\n📅 Sana: {data['date']}\n⏰ Vaqt: {slot}")
    await state.clear()
    await cb.answer()

# --- Jamoa buyrug'i ---
@dp.message(F.text == "Jamoa 🤝")
async def team_info(message: types.Message):
    await message.answer("Jamoa funksiyasi tez orada ishga tushiriladi... ⚽️")

# --- Mening Bronlarim ---
@dp.message(F.text == "Mening Bronlarim")
async def my_bookings(message: types.Message):
    bookings = db.get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer("Sizda hali bronlar mavjud emas.")
        return
    
    text = "📅 **Sizning bronlaringiz:**\n"
    for b in bookings:
        text += f"\n🏟 {b[2]}\n🗓 Sana: {b[0]}\n⏰ Vaqt: {b[1]}\n📍 [Google Maps]({b[3]})\n"
    
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

# --- Profil ---
@dp.message(F.text == "Profil")
async def show_profile(message: types.Message):
    u = db.get_user(message.from_user.id)
    role = "Stadion Egasi" if u[3] else "Mijoz"
    await message.answer(f"👤 **Profilingiz:**\n\n🆔 ID: {u[0]}\n👤 Ism: {u[1]}\n🎭 Rol: {role}")

# --- Stadion Egasi: Stadion Qo'shish ---
@dp.message(F.text == "Stadion Qo'shish")
async def add_st_start(message: types.Message, state: FSMContext):
    await message.answer("Stadion nomini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSt.name)

@dp.message(AddSt.name)
async def add_st_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Google Maps linkini kiriting:")
    await state.set_state(AddSt.link)

@dp.message(AddSt.link)
async def add_st_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]], resize_keyboard=True)
    await message.answer("Stadion lokatsiyasini tugma orqali yuboring:", reply_markup=kb)
    await state.set_state(AddSt.loc)

@dp.message(AddSt.loc, F.location)
async def add_st_loc(message: types.Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
    await message.answer("Bir soatlik o'yin narxini kiriting (faqat raqam, masalan: 100000):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSt.price)

@dp.message(AddSt.price)
async def add_st_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Ish vaqtini kiriting (format: 09:00-22:00):")
    await state.set_state(AddSt.hours)

@dp.message(AddSt.hours)
async def add_st_hours(message: types.Message, state: FSMContext):
    await state.update_data(hours=message.text)
    await message.answer("Stadion rasmini yuboring:")
    await state.set_state(AddSt.photo)

@dp.message(AddSt.photo, F.photo)
async def add_st_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    db.add_stadium(message.from_user.id, data['name'], data['link'], data['lat'], data['lon'], data['price'], data['hours'], photo_id)
    await message.answer("✅ Stadion muvaffaqiyatli qo'shildi!", reply_markup=main_menu(True))
    await state.clear()

@dp.message(F.text == "Mening Stadionlarim")
async def owner_stadiums(message: types.Message):
    stadiums = db.get_owner_stadiums(message.from_user.id)
    if not stadiums:
        await message.answer("Sizda hali ro'yxatdan o'tgan stadionlar yo'q.")
        return
    for s in stadiums:
        await message.answer_photo(s[8], caption=f"🏟 **{s[2]}**\n💰 Narxi: {s[6]:,} so'm\n⏰ Ish vaqti: {s[7]}\n📍 [Xarita Link]({s[3]})", parse_mode="Markdown")

# --- Asosiy funksiya ---
async def main():
    # Render uchun soxta serverni ishga tushirish
    await start_web_server()
    # Botni ishga tushirish
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
        
