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

# Logging
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
class EditSt(StatesGroup): id = State(); name = State(); price = State(); hours = State(); addr = State(); desc = State()
class Book(StatesGroup): sid = State(); date = State(); time = State()
class GoalState(StatesGroup): bid = State(); goals = State()

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
    await message.answer(f"Siz {message.text} bo'lib ro'yxatdan o'tdingiz.", reply_markup=main_menu(is_owner))
    await state.clear()

# --- Stadium Management ---
@dp.message(F.text == "Stadion Qo'shish")
async def add_st_start(message: types.Message, state: FSMContext):
    await message.answer("Stadion nomi:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSt.name)

@dp.message(AddSt.name)
async def add_st_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Manzil:")
    await state.set_state(AddSt.addr)

@dp.message(AddSt.addr)
async def add_st_addr(message: types.Message, state: FSMContext):
    await state.update_data(addr=message.text)
    await message.answer("Lokatsiya yuboring:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Lokatsiya", request_location=True)]], resize_keyboard=True))
    await state.set_state(AddSt.loc)

@dp.message(AddSt.loc, F.location)
async def add_st_loc(message: types.Message, state: FSMContext):
    await state.update_data(lat=message.location.latitude, lon=message.location.longitude)
    await message.answer("Narxi (soatiga):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddSt.price)

@dp.message(AddSt.price)
async def add_st_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Ish vaqti (08:00-23:00):")
    await state.set_state(AddSt.hours)

@dp.message(AddSt.hours)
async def add_st_hours(message: types.Message, state: FSMContext):
    await state.update_data(hours=message.text)
    await message.answer("Tavsif:")
    await state.set_state(AddSt.desc)

@dp.message(AddSt.desc)
async def add_st_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Rasm yuboring:")
    await state.set_state(AddSt.photo)

@dp.message(AddSt.photo, F.photo)
async def add_st_photo(message: types.Message, state: FSMContext):
    d = await state.get_data()
    db.add_stadium(message.from_user.id, d['name'], d['addr'], d['lat'], d['lon'], d['price'], d['desc'], message.photo[-1].file_id, d['hours'])
    await message.answer("✅ Stadion qo'shildi!", reply_markup=main_menu(True))
    await state.clear()

@dp.message(F.text == "Mening Stadionlarim")
async def my_stadiums(message: types.Message):
    stadiums = db.get_owner_stadiums(message.from_user.id)
    if not stadiums: return await message.answer("Sizda stadionlar yo'q.")
    for s in stadiums:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Tahrirlash 📝", callback_data=f"est_{s[0]}"), InlineKeyboardButton(text="O'chirish ❌", callback_data=f"dst_{s[0]}")]])
        await message.answer(f"🏟 {s[2]}\n💰 {s[6]:,} so'm\n⏰ {s[9]}", reply_markup=kb)

@dp.callback_query(F.data.startswith("dst_"))
async def del_stadium(cb: types.CallbackQuery):
    db.delete_stadium(int(cb.data.split("_")[1]))
    await cb.message.delete()
    await cb.answer("O'chirildi")

# --- User Side: List & Book ---
@dp.message(F.text == "Barcha Stadionlar")
@dp.message(F.location)
async def list_st(message: types.Message):
    stadiums = db.get_all_stadiums()
    if not stadiums: return await message.answer("Stadionlar yo'q.")
    u_loc = (message.location.latitude, message.location.longitude) if message.location else None
    if u_loc:
        db.cursor.execute("UPDATE users SET latitude=?, longitude=? WHERE id=?", (u_loc[0], u_loc[1], message.from_user.id))
        db.connection.commit()
        stadiums = sorted(stadiums, key=lambda s: geodesic(u_loc, (s[4], s[5])).km)[:5]

    for s in stadiums:
        dist = f"📏 {geodesic(u_loc, (s[4], s[5])).km:.2f} km\n" if u_loc else ""
        text = f"🏟 {s[2]}\n{dist}💰 {s[6]:,} so'm\n⏰ {s[9]}\n📍 {s[3]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bron qilish", callback_data=f"book_{s[0]}")]])
        await message.answer_photo(s[8], caption=text, reply_markup=kb)

@dp.callback_query(F.data.startswith("book_"))
async def start_book(cb: types.CallbackQuery, state: FSMContext):
    sid = int(cb.data.split("_")[1])
    await state.update_data(sid=sid)
    await cb.message.answer("Sana (YYYY-MM-DD):")
    await state.set_state(Book.date)

@dp.message(Book.date)
async def book_date(message: types.Message, state: FSMContext):
    d = await state.get_data()
    bookings = db.get_stadium_bookings(d['sid'], message.text)
    s = db.get_stadium_by_id(d['sid'])
    booked = ", ".join([f"{b[0]}-{b[1]}" for b in bookings]) if bookings else "Bo'sh"
    await state.update_data(date=message.text)
    await message.answer(f"🏟 {s[2]}\n⏰ Ish vaqti: {s[9]}\n🚫 Band: {booked}\n\nVaqtni kiriting (18:00-19:00):")
    await state.set_state(Book.time)

@dp.message(Book.time)
async def book_time(message: types.Message, state: FSMContext):
    d = await state.get_data()
    start, end = message.text.split("-")
    link = f"join_{message.from_user.id}_{d['sid']}_{datetime.now().microsecond}"
    b_id = db.add_booking(message.from_user.id, d['sid'], d['date'], start, end, link)
    bot_un = (await bot.get_me()).username
    await message.answer(f"✅ Bron qilindi!\n🤝 Jamoa linki:\nhttps://t.me/{bot_un}?start={link}", reply_markup=main_menu( ))
    await state.clear()
    asyncio.create_task(game_survey(message.from_user.id, b_id))

# --- Game Survey & Stats ---
async def game_survey(u_id, b_id):
    await asyncio.sleep(60) # Test uchun 1 daqiqa (realda o'yin vaqtida bo'ladi)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ha", callback_data=f"gs_y_{b_id}"), InlineKeyboardButton(text="Yo'q", callback_data=f"gs_n_{b_id}")]])
    await bot.send_message(u_id, "⚽️ O'yin boshlandimi?", reply_markup=kb)

@dp.callback_query(F.data.startswith("gs_y_"))
async def gs_yes(cb: types.CallbackQuery, state: FSMContext):
    b_id = int(cb.data.split("_")[2])
    await state.update_data(bid=b_id)
    await cb.message.answer("Nechta gol urdingiz?")
    await state.set_state(GoalState.goals)

@dp.message(GoalState.goals)
async def set_goals(message: types.Message, state: FSMContext):
    d = await state.get_data()
    goals = int(message.text) if message.text.isdigit() else 0
    members = db.get_team_members(d['bid'])
    for m in members:
        db.update_stats(m[0], goals if m[0] == message.from_user.id else 0)
    await message.answer("✅ Statistika yangilandi!", reply_markup=main_menu())
    await state.clear()

# --- User Bookings & Teams ---
@dp.message(F.text == "Mening Bronlarim")
async def my_books(message: types.Message):
    books = db.get_user_bookings(message.from_user.id)
    if not books: return await message.answer("Bronlar yo'q.")
    for b in books:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Bekor qilish ❌", callback_data=f"can_{b[0]}")]])
        await message.answer(f"🏟 {b[10]}\n📅 {b[3]} | ⏰ {b[4]}-{b[5]}", reply_markup=kb)

@dp.callback_query(F.data.startswith("can_"))
async def cancel_book(cb: types.CallbackQuery):
    db.cancel_booking(int(cb.data.split("_")[1]))
    await cb.message.edit_text("❌ Bekor qilindi")

@dp.message(F.text == "Jamoa 🤝")
async def team_view(message: types.Message):
    teams = db.get_user_teams(message.from_user.id)
    if not teams: return await message.answer("Siz a'zo bo'lgan faol jamoalar yo'q.")
    for t in teams:
        m = db.get_team_members(t[0])
        m_list = "\n".join([f"👤 {u[1]}" for u in m])
        await message.answer(f"🏟 {t[10]}\n📅 {t[3]} | ⏰ {t[4]}-{t[5]}\n\n👥 Ishtirokchilar:\n{m_list}")

@dp.message(F.text == "Profil")
async def profile(message: types.Message):
    u = db.get_user(message.from_user.id)
    text = f"👤 {u[1]}\n🎭 Rol: {'Egasi' if u[3] else 'Mijoz'}\n⚽️ O'yinlar: {u[6]}\n🥅 Gollari: {u[7]}"
    await message.answer(text)

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
    
