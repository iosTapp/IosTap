import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8613472750:AAHp5HMZsjjMSTqv1cB96l7aGqwykqI14sQ"  # Токен от @BotFather
ADMIN_IDS = [6242943729]  # Ваш Telegram ID (число). При необходимости замените на свой.

BOT_NAME = "iOS TAP"
FREE_BONUS_AMOUNT = 1.0  # Ежедневный бонус 1 рубль
PREMIUM_FILE_PRICE = 300.0  # Стоимость платного файла 300 рублей[span_0](start_span)[span_0](end_span)
REFERRAL_BONUS = 5.0  # Награда за реферала
SUPPORT_CONTACT = "uicacherr"  # Владелец и поддержка (без @ для t.me/)
# ======================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# --- БАЗА ДАННЫХ (SQLite) ---
def db_init():
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            referrer_id INTEGER DEFAULT NULL,
            ref_count INTEGER DEFAULT 0
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_type TEXT, -- 'free' или 'premium'
            file_id TEXT,
            file_name TEXT,
            caption TEXT
        )
    """
    )
    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res


def add_user(user_id: int, username: str, referrer_id: int = None):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    if not get_user(user_id):
        cursor.execute(
            "INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
            (user_id, username, referrer_id),
        )
        if referrer_id and get_user(referrer_id):
            cursor.execute(
                "UPDATE users SET balance = balance + ?, ref_count = ref_count + 1 WHERE user_id = ?",
                (REFERRAL_BONUS, referrer_id),
            )
        conn.commit()
    conn.close()


def update_balance(user_id: int, amount: float):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()


def save_file_to_db(file_type: str, file_id: str, file_name: str, caption: str):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    # Перезаписываем или добавляем новый файл определенного типа
    cursor.execute("DELETE FROM files WHERE file_type = ?", (file_type,))
    cursor.execute(
        "INSERT INTO files (file_type, file_id, file_name, caption) VALUES (?, ?, ?, ?)",
        (file_type, file_id, file_name, caption),
    )
    conn.commit()
    conn.close()


def get_file_from_db(file_type: str):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_name, caption FROM files WHERE file_type = ?", (file_type,))
    res = cursor.fetchone()
    conn.close()
    return res


# --- FSM СОСТОЯНИЯ ---
class AdminStates(StatesGroup):
    wait_for_broadcast = State()
    wait_for_give_id = State()
    wait_for_give_amount = State()
    wait_for_file_type = State()
    wait_for_file_document = State()
    wait_for_news_text = State()


# --- КЛАВИАТУРЫ ---
def main_keyboard(user_id: int):
    kb = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Free Бонус")],
        [
            KeyboardButton(text="📂 Бесплатный файл"),
            KeyboardButton(text="💎 Платный файл"),
        ],
        [
            KeyboardButton(text="💳 Пополнить баланс"),
            KeyboardButton(text="👥 Рефералка"),
        ],
    ]
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton(text="⚡ iOS TAP Admin")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data="admin_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📂 Загрузить / Обновить файл", callback_data="admin_upload_file"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📰 Опубликовать новость", callback_data="admin_news"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Выдать баланс", callback_data="admin_give_balance"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Рассылка", callback_data="admin_broadcast"
                )
            ],
        ]
    )


def profile_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💬 Написать админу (@{SUPPORT_CONTACT})",
                    url=f"https://t.me/{SUPPORT_CONTACT}",
                )
            ]
        ]
    )


# --- ОБРАБОТКА КОМАНД ---


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Пользователь"

    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        candidate = int(args[1])
        if candidate != user_id:
            referrer_id = candidate

    add_user(user_id, username, referrer_id)

    welcome_text = (
        f"  <b>{BOT_NAME} — Standoff 2 Hub</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Привет, <b>{message.from_user.first_name}</b>!\n"
        f"Лучшие модификации, скрипты и читы для iOS & Android.\n\n"
        f"👇 Выберите нужный раздел в меню ниже:"
    )

    await message.answer(
        welcome_text,
        reply_markup=main_keyboard(user_id),
        parse_mode="HTML",
    )


# --- ПРОФИЛЬ И БОНУСЫ ---


@dp.message(F.text == "👤 Профиль")
async def show_profile(message: types.Message):
    user = get_user(message.from_user.id)
    if user:
        _, username, balance, _, ref_count = user
        profile_text = (
            f"  <b>ЛИЧНЫЙ КАБИНЕТ // iOS TAP</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Имя:</b> {message.from_user.first_name}\n"
            f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
            f"💳 <b>Баланс:</b> <code>{balance:.2f} ₽</code>\n"
            f"👥 <b>Приглашено:</b> {ref_count} чел.\n"
            f"━━━━━━━━━━━━━━━━━━━━━"
        )
        await message.answer(
            profile_text,
            reply_markup=profile_inline_keyboard(),
            parse_mode="HTML",
        )


@dp.message(F.text == "🎁 Free Бонус")
async def get_free_bonus(message: types.Message):
    update_balance(message.from_user.id, FREE_BONUS_AMOUNT)
    text = (
        f"🎉  <b>БОНУС УСПЕШНО ПОЛУЧЕН</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"На ваш баланс зачислено: <b>+{FREE_BONUS_AMOUNT} ₽</b>\n"
        f"Возвращайтесь завтра за новой порцией бонусов!"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "👥 Рефералка")
async def show_ref(message: types.Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    ref_text = (
        f"👥  <b>РЕФЕРАЛЬНАЯ СИСТЕМА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Приглашайте друзей по вашей уникальной ссылке и получайте бонусы на счет.\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(ref_text, parse_mode="HTML")


# --- ПОПОЛНЕНИЕ БАЛАНСА ---


@dp.message(F.text == "💳 Пополнить баланс")
async def start_deposit(message: types.Message):
    deposit_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💳 Пополнить через @{SUPPORT_CONTACT}",
                    url=f"https://t.me/{SUPPORT_CONTACT}",
                )
            ]
        ]
    )
    text = (
        f"💳  <b>ПОПОЛНЕНИЕ СЧЕТА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Для пополнения баланса и активации платных читов Standoff 2 нажмите на кнопку ниже и напишите нашему менеджеру:\n\n"
        f"👉 <b>Контакт:</b> @{SUPPORT_CONTACT}"
    )
    await message.answer(text, reply_markup=deposit_keyboard, parse_mode="HTML")


# --- ВЫДАЧА ФАЙЛОВ ---


@dp.message(F.text == "📂 Бесплатный файл")
async def send_free_file(message: types.Message):
    file_data = get_file_from_db("free")
    if not file_data:
        # Заглушка, если админ еще ничего не загрузил
        file_payload = (
            b"UT Payload/VelyaTap.app/zh-Hans.lproj/Localizable.strings "
            b"iOS TAP Free Standoff 2 Config Content Data Payload"
        )
        await message.answer_document(
            BufferedInputFile(file_payload, filename="VelyaTap_Free_Config.ipa"),
            caption=(
                f"📂  <b>БЕСПЛАТНЫЙ КОНФИГ ГОТОВ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"Приватная сборка успешно загружена.\n"
                f"💬 Поддержка и покупка: @{SUPPORT_CONTACT}"
            ),
            parse_mode="HTML",
        )
    else:
        file_id, file_name, caption = file_data
        cap = caption or f"📂  <b>БЕСПЛАТНЫЙ ФАЙЛ</b>\n💬 Поддержка: @{SUPPORT_CONTACT}"
        await message.answer_document(file_id, caption=cap, parse_mode="HTML")


@dp.message(F.text == "💎 Платный файл")
async def send_premium_file(message: types.Message):
    user = get_user(message.from_user.id)
    balance = user[2]

    if balance < PREMIUM_FILE_PRICE:
        no_money_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💬 Купить / Пополнить (@{SUPPORT_CONTACT})",
                        url=f"https://t.me/{SUPPORT_CONTACT}",
                    )
                ]
            ]
        )
        await message.answer(
            f"❌  <b>НЕДОСТАТОЧНО СРЕДСТВ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 Стоимость чита: <b>{PREMIUM_FILE_PRICE} ₽</b>\n"
            f"💳 Ваш баланс: <b>{balance:.2f} ₽</b>\n\n"
            f"Для пополнения счета обратитесь к администратору.",
            reply_markup=no_money_keyboard,
            parse_mode="HTML",
        )
    else:
        update_balance(message.from_user.id, -PREMIUM_FILE_PRICE)
        await message.answer("💎 <i>Оплата списана с баланса. Выдача премиум-файла...</i>", parse_mode="HTML")

        file_data = get_file_from_db("premium")
        if not file_data:
            premium_payload = (
                b"UT Payload/VelyaTap.app/VelyaTap "
                b"iOS TAP PREMIUM Standoff 2 Cheat Payload - Access Granted"
            )
            await message.answer_document(
                BufferedInputFile(premium_payload, filename="VelyaTap_Premium_Cheat.ipa"),
                caption=(
                    f"💎  <b>ПРЕМИУМ ЧИТ УСПЕШНО КУПЛЕН</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Переход к покупке завершен.\n"
                    f"💬 Связь с разработчиком: @{SUPPORT_CONTACT}"
                ),
                parse_mode="HTML",
            )
        else:
            file_id, file_name, caption = file_data
            cap = caption or f"💎  <b>ПРЕМИУМ ЧИТ</b>\n💬 Связь: @{SUPPORT_CONTACT}"
            await message.answer_document(file_id, caption=cap, parse_mode="HTML")


# --- АДМИН ПАНЕЛЬ И ЗАГРУЗКА ФАЙЛОВ / НОВОСТЕЙ ---


@dp.message(F.text == "⚡ iOS TAP Admin")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "⚡  <b>АДМИН-ПАНЕЛЬ iOS TAP</b>\nВыберите действие:",
        reply_markup=admin_inline_keyboard(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(balance) FROM users")
    total_users, total_balance = cursor.fetchone()
    conn.close()

    total_balance = total_balance if total_balance else 0.0
    stats_text = (
        f"📊  <b>СТАТИСТИКА СИСТЕМЫ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"💰 Общий баланс: <b>{total_balance:.2f} ₽</b>"
    )
    await call.message.answer(stats_text, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "admin_upload_file")
async def admin_upload_file_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📂 Бесплатный файл", callback_data="set_type_free"),
                InlineKeyboardButton(text="💎 Платный файл", callback_data="set_type_premium"),
            ]
        ]
    )
    await call.message.answer("📂 Выберите тип файла, который хотите загрузить или обновить:", reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("set_type_"))
async def admin_set_file_type(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    f_type = call.data.split("_")[2]  # free или premium
    await state.update_data(file_type=f_type)
    await state.set_state(AdminStates.wait_for_file_document)
    
    await call.message.answer(
        f"📤 Отправьте файл (документ/IPA/архив) для категории: <b>{'Бесплатный' if f_type=='free' else 'Платный'}</b>.\n"
        "К сообщению с файлом можете добавить подпись (caption), она будет выводиться пользователям.",
        parse_mode="HTML"
    )
    await call.answer()


@dp.message(AdminStates.wait_for_file_document, F.document)
async def admin_receive_file(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    file_type = data.get("file_type")

    document = message.document
    file_id = document.file_id
    file_name = document.file_name or "file.ipa"
    caption = message.caption or ""

    save_file_to_db(file_type, file_id, file_name, caption)
    await message.answer(
        f"✅ Файл для категории <b>{'Бесплатный' if file_type=='free' else 'Платный'}</b> успешно сохранен в базе!",
        parse_mode="HTML"
    )
    await state.clear()


@dp.message(AdminStates.wait_for_file_document)
async def admin_wrong_file_type(message: types.Message):
    await message.answer("❌ Пожалуйста, отправьте именно файл (документ).")


# Публикация новостей
@dp.callback_query(F.data == "admin_news")
async def admin_news_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.wait_for_news_text)
    await call.message.answer("📰 Введите текст новости или обновления. Он будет отправлен всем пользователям бота в виде рассылки:")
    await call.answer()


@dp.message(AdminStates.wait_for_news_text)
async def process_news(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    news_text = f"🚨 <b>НОВОСТИ И ОБНОВЛЕНИЯ // iOS TAP</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n{message.text}"

    count = 0
    for u in users:
        try:
            await bot.send_message(u[0], news_text, parse_mode="HTML")
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Новость успешно опубликована и разослана {count} пользователям.")
    await state.clear()


@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.wait_for_broadcast)
    await call.message.answer("📢 Введите текст рассылки для всех пользователей:")
    await call.answer()


@dp.message(AdminStates.wait_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    conn = sqlite3.connect("ios_tap_so2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    count = 0
    for u in users:
        try:
            await bot.send_message(u[0], message.text)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Рассылка отправлена {count} пользователям.")
    await state.clear()


@dp.callback_query(F.data == "admin_give_balance")
async def start_give_balance(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.wait_for_give_id)
    await call.message.answer("Введите <b>ID пользователя</b>:", parse_mode="HTML")
    await call.answer()


@dp.message(AdminStates.wait_for_give_id)
async def process_give_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID должен состоять только из цифр.")
        return
    await state.update_data(target_id=int(message.text))
    await state.set_state(AdminStates.wait_for_give_amount)
    await message.answer("Введите сумму (можно с минусом для списания):")


@dp.message(AdminStates.wait_for_give_amount)
async def process_give_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        target_id = data["target_id"]

        update_balance(target_id, amount)
        await message.answer(
            f"✅ Баланс пользователя <code>{target_id}</code> изменен на <b>{amount} ₽</b>.",
            parse_mode="HTML",
        )
        try:
            await bot.send_message(
                target_id, f"💳 Ваш баланс был изменен администратором на <b>{amount} ₽</b>.", parse_mode="HTML"
            )
        except Exception:
            pass
        await state.clear()
    except ValueError:
        await message.answer("❌ Укажите корректную сумму числом.")


# --- ЗАПУСК ---
async def main():
    db_init()
    print("🚀 Бот iOS TAP запущен и полностью настроен под @uicacherr!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
