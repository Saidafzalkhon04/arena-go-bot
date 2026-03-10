import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from geopy.distance import geodesic
from aiohttp import web
from datetime import datetime

from db import Database

logging.basicConfig(level=logging.INFO )
TOKEN = "8724037162:AAHoxj_-NSO96BnoL7O85WlPDiBYSmQFqUU"
db = Database("arena_go.db")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Render Port Fix ---
async def handle(request): return web.Response(text="Bot is running!")
async def start_web_server():
    app = web.Application(); app.router.add_get("/", handle)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()

# --- States ---
class Reg(StatesGroup): role = State()
class AddSt(StatesGroup): name = State(); addr = State(); loc = State(); price = State(); hours = State(); desc = State(); photo = State()
class EditSt(StatesGroup): id = State(); price = State(); hours = State()
class Book(StatesGroup): sid = State(); date = State(); time = State()

# --- Keyboards ---
def main_menu(is_owner=False):
    kb = []
    if is_owner:
        kb.append([KeyboardButton(text="Mening Stadionlarim"), KeyboardButton(text="Stadion Qo'shish")])
    else:
        kb.append([KeyboardButton(text="Yaqin Stadionlar", request_location=True), KeyboardButton(text="Barcha Stadionlar")])
        kb.append([KeyboardButton(text="Jamoa 🤝"), KeyboardButton(text="Mening Bronlarim")])
    kb.append([KeyboardButton(text="Profil")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- Handlers ---
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    args = message.text.split()
    user = db.get_user(message.from_user.id)
    if not user:
        db.add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    
    if len(args) > 1 and args[1].startswith("join_"):
        booking = db.get_booking_by_link(args[1])
        if booking:
            db.add_team_member(booking[0], message.from_user.id)
            stadium = db.get_stadium_by_id(booking[2])
            await message.answer(f"✅ Jamoaga qo'shildingiz!\n🏟 {stadium[2]}\n📅 {booking[3]} | ⏰ {booking[4]}-{booking[5]}")
            await bot.send_location(message.from_user.id, stadium[4], stadium[5])
            return

    await message.answer("Xush kelibsiz! Rolni tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Mijoz"), KeyboardButton(text="Stadion Egasi")]], resize_keyboard=True))
    await state.set_state(Reg.role)

@dp.message(Reg.role)
async def set_role(message: types.Message, state: FSMContext):
    is_owner = 1 if message.text == "Stadion Egasi" else 0
    db.cursor.execute("UPDATE users SET is_owner=? WHERE id=?", (is_owner, message.from_user.id))
    db.connection.commit()
    await message.answer(f"Siz {message.text} sifatida ro'yxatdan o'tdingiz.", reply_markup=main_menu(is_owner))
    await state.clear()

# --- Stadium Handlers ---
@dp.message(F.text == "Barcha Stadionlar")
@dp.message(F.location)
async def list_stadiums(message: types.Message):
    stadiums = db.get_all_stadiums()
    if not stadiums: return await message.answer("Hozircha stadionlar yo'q.")
    
    u_loc = (message.location.latitude, message.location.longitude) if message.location else None
    if u_loc:
        stadiums = sorted(stadiums, key=lambda s: geodesic(u_loc, (s[4], s[5])).km)[:5]

    for s in stadiums:
        dist = f"📏 {geodesic(u_loc, (s[4], s[5])).km:.2f} km\n" if u_loc else ""
        text = f"🏟 {s[2]}\n{dist}💰 {s[6]:,} so'm\n⏰ {s[9]}\n📍 {s[3]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bron qilish", callback_data=f"book_{s[0]}")], [InlineKeyboardButton(text="📍 Lokatsiya", callback_data=f"sloc_{s[0]}")]])
        await message.answer_photo(s[8], caption=text, reply_markup=kb)

@dp.callback_query(F.data.startswith("sloc_"))
async def send_st_loc(cb: types.CallbackQuery):
    s = db.get_stadium_by_id(int(cb.data.split("_")[1]))
    await bot.send_location(cb.from_user.id, s[4], s[5])
    await cb.answer()

@dp.callback_query(F.data.startswith("book_"))
async def start_book(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(sid=int(cb.data.split("_")[1]))
    await cb.message.answer("Sana (YYYY-MM-DD):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Book.date)

@dp.message(Book.date)
async def book_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Vaqtni kiriting (masalan: 18:00-19:00):")
    await state.set_state(Book.time)

@dp.message(Book.time)
async def book_time(message: types.Message, state: FSMContext):
    d = await state.get_data()
    start, end = message.text.split("-")
    if db.check_availability(d['sid'], d['date'], start, end):
        link = f"join_{message.from_user.id}_{d['sid']}_{datetime.now().microsecond}"
        db.add_booking(message.from_user.id, d['sid'], d['date'], start, end, link)
        bot_un = (await bot.get_me()).username
        await message.answer(f"✅ Bron qilindi!\n🤝 Jamoa linki:\nhttps://t.me/{bot_un}?start={link}", reply_markup=main_menu( ))
        await state.clear()
    else:
        await message.answer("❌ Bu vaqt band! Boshqa vaqt tanlang.")

# --- Owner Management ---
@dp.message(F.text == "Stadion Qo'shish")
async def add_st_start(message: types.Message, state: FSMContext):
    await message.answer("Stadion nomi:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSt.name)

@dp.message(AddSt.name)
async def add_st_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text); await message.answer("Manzil:"); await state.set_state(AddSt.addr)

@dp.message(AddSt.addr)
async def add_st_addr(message: types.Message, state: FSMContext):
    await state.update_data(addr=message.text); await message.answer("Lokatsiya yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Lokatsiya", request_location=True)]], resize_keyboard=True)); await state.set_state(AddSt.loc)

@dp.message(AddSt.loc, F.location)
async def add_st_loc(message: types.Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude); await message.answer("Narxi (soatiga):", reply_markup=ReplyKeyboardRemove()); await state.set_state(AddSt.price)

@dp.message(AddSt.price)
async def add_st_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text); await message.answer("Ish vaqti (08:00-23:00):"); await state.set_state(AddSt.hours)

@dp.message(AddSt.hours)
async def add_st_hours(message: types.Message, state: FSMContext):
    await state.update_data(hours=message.text); await message.answer("Tavsif:"); await state.set_state(AddSt.desc)

@dp.message(AddSt.desc)
async def add_st_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text); await message.answer("Rasm yuboring:"); await state.set_state(AddSt.photo)

@dp.message(AddSt.photo, F.photo)
async def add_st_photo(message: types.Message, state: FSMContext):
    d = await state.get_data()
    db.add_stadium(message.from_user.id, d['name'], d['addr'], d['lat'], d['lon'], d['price'], d['desc'], message.photo[-1].file_id, d['hours'])
    await message.answer("✅ Stadion qo'shildi!", reply_markup=main_menu(True)); await state.clear()

@dp.message(F.text == "Mening Stadionlarim")
async def my_stadiums(message: types.Message):
    stadiums = db.get_owner_stadiums(message.from_user.id)
    if not stadiums: return await message.answer("Sizda stadionlar yo'q.")
    for s in stadiums:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Tahrirlash 📝", callback_data=f"edit_{s[0]}"), InlineKeyboardButton(text="O'chirish ❌", callback_data=f"del_{s[0]}")]])
        await message.answer_photo(s[8], caption=f"🏟 {s[2]}\n💰 {s[6]:,} so'm\n⏰ {s[9]}", reply_markup=kb)

@dp.callback_query(F.data.startswith("edit_"))
async def edit_st_start(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(sid=int(cb.data.split("_")[1]))
    await cb.message.answer("Yangi narxni kiriting:")
    await state.set_state(EditSt.price); await cb.answer()

@dp.message(EditSt.price)
async def edit_st_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text); await message.answer("Yangi ish vaqtini kiriting (08:00-23:00):"); await state.set_state(EditSt.hours)

@dp.message(EditSt.hours)
async def edit_st_hours(message: types.Message, state: FSMContext):
    d = await state.get_data()
    db.update_stadium(d['sid'], d['price'], message.text)
    await message.answer("✅ Yangilandi!", reply_markup=main_menu(True)); await state.clear()

@dp.callback_query(F.data.startswith("del_"))
async def del_st(cb: types.CallbackQuery):
    db.delete_stadium(int(cb.data.split("_")[1])); await cb.message.delete(); await cb.answer("O'chirildi")

# --- Profil & Jamoa ---
@dp.message(F.text == "Profil")
async def profile(message: types.Message):
    u = db.get_user(message.from_user.id)
    is_owner = bool(u[3])
    text = f"👤 **Profil:**\n🆔 ID: {u[0]}\n👤 Ism: {u[1]}\n🎭 Rol: {'Stadion Egasi' if is_owner else 'Mijoz'}"
    await message.answer(text)
    if is_owner:
        stadiums = db.get_owner_stadiums(u[0])
        for s in stadiums:
            await message.answer_photo(s[8], caption=f"🏟 **Sizning stadiningiz:**\nNomi: {s[2]}\nManzil: {s[3]}\n💰 Narxi: {s[6]:,} so'm\n⏰ Ish vaqti: {s[9]}")

@dp.message(F.text == "Mening Bronlarim")
async def my_books(message: types.Message):
    books = db.get_user_bookings(message.from_user.id)
    if not books: return await message.answer("Bronlar yo'q.")
    for b in books:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bekor qilish ❌", callback_data=f"can_{b[0]}")]])
        await message.answer(f"🏟 {b[9]}\n📅 {b[3]} | ⏰ {b[4]}-{b[5]}", reply_markup=kb)

@dp.callback_query(F.data.startswith("can_"))
async def cancel_book(cb: types.CallbackQuery):
    db.cancel_booking(int(cb.data.split("_")[1])); await cb.message.edit_text("❌ Bekor qilindi"); await cb.answer()

@dp.message(F.text == "Jamoa 🤝")
async def team_view(message: types.Message):
    await message.answer("Siz a'zo bo'lgan jamoalarni ko'rish uchun 'Mening Bronlarim' orqali linkni ulashing.")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
            
