from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

API_TOKEN = '8400720613:AAHUxRixbHWQhP-XKEEob2gS1wJp5pSd_YI'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class Deal(StatesGroup):
    waiting_for_amount = State()

deals = {}

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split(" ")
    
    if len(parts) > 1 and parts[1].startswith("join_"):
        owner_id_str = parts[1].replace("join_", "")
        try:
            owner_id = int(owner_id_str)
        except ValueError:
            await message.answer("❌ Неверная ссылка.")
            return

        if str(owner_id) not in deals:
            await message.answer("❌ Сделка не найдена или истекла.")
            return

        if 'partner_id' in deals[str(owner_id)]:
            await message.answer("⚠ В сделку уже вступил другой пользователь.")
            return

        deals[str(owner_id)]['partner_id'] = message.from_user.id
        deals[str(owner_id)]['partner_confirmed'] = False
        deals[str(owner_id)]['owner_confirmed'] = False
        deals[str(owner_id)]['payment_confirmed'] = False  # Новый флаг

        await message.answer(f"✅ Вы успешно вступили в сделку с пользователем с ID {owner_id}.")

        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton(text="💸 Оплатить", callback_data=f"pay_{owner_id}"),
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_owner_{owner_id}")
        )
        try:
            await bot.send_message(owner_id,
                f"👤 Пользователь @{message.from_user.username or message.from_user.id} вступил в сделку.\n\nВот кнопки управления сделкой:",
                reply_markup=keyboard)
        except:
            pass

        keyboard_partner = InlineKeyboardMarkup(row_width=1)
        keyboard_partner.add(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_partner_{owner_id}")
        )
        await message.answer("Нажмите кнопку ниже, чтобы подтвердить сделку:", reply_markup=keyboard_partner)
        return

    await message.answer("👋 Привет, я бот-гарант по сделкам.\n\nНапиши, на сколько звёзд будет сделка (от 25 до 10000):")
    await Deal.waiting_for_amount.set()

@dp.message_handler(state=Deal.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 25 or amount > 10000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 25 до 10000.")
        return

    owner_id = message.from_user.id
    deals[str(owner_id)] = {
        'amount': amount,
        'partner_confirmed': False,
        'owner_confirmed': False,
        'payment_confirmed': False
    }

    bot_username = (await bot.get_me()).username

    join_link = f"https://t.me/{bot_username}?start=join_{owner_id}"

    await message.answer(
        f"Сделка на {amount} звёзд создана.\n"
        f"Отправьте эту ссылку партнёру для вступления:\n\n{join_link}"
    )
    await state.finish()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith(("confirm_owner_", "confirm_partner_", "pay_")))
async def process_callback_confirm_pay(callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if data.startswith("confirm_owner_"):
        owner_id = int(data.split("_")[-1])
        if str(owner_id) not in deals:
            await callback_query.answer("❌ Сделка не найдена или истекла.", show_alert=True)
            return

        if user_id != owner_id:
            await callback_query.answer("⚠ Только владелец сделки может подтвердить этим.", show_alert=True)
            return

        deal = deals[str(owner_id)]

        # Если ещё не было подтверждения оплаты
        if not deal['payment_confirmed']:
            # Проверяем, вступил ли партнёр и подтвердил ли он сделку
            partner_id = deal.get('partner_id')
            if partner_id is None:
                await callback_query.answer("❌ Партнёр ещё не вступил в сделку.", show_alert=True)
                return
            if not deal.get('partner_confirmed'):
                await callback_query.answer("⚠ Партнёр ещё не подтвердил сделку.", show_alert=True)
                return

            # Владелец подтверждает, что перевёл звёзды — подтверждение оплаты
            deal['payment_confirmed'] = True

            # Отправляем партнёру финальное сообщение
            amount = deal['amount']
            await bot.send_message(partner_id,
                f"✅ Сделка на {amount}⭐ успешно завершена, пользователь оплатил {amount} звезд.\n"
                f"Чтобы получить оплату, передайте товар нашему менеджеру @meneger_garantbott\n"
                f"После этого вы автоматически получите вашу оплату. Хорошего дня!")

            await callback_query.answer("Вы подтвердили оплату. Сделка завершена.")
            return

        # Если уже была оплата — просто уведомляем
        await callback_query.answer("Вы уже подтвердили оплату.", show_alert=True)


    elif data.startswith("confirm_partner_"):
        owner_id = int(data.split("_")[-1])
        if str(owner_id) not in deals:
            await callback_query.answer("❌ Сделка не найдена или истекла.", show_alert=True)
            return

        deal = deals[str(owner_id)]
        partner_id = deal.get('partner_id')

        if user_id != partner_id:
            await callback_query.answer("⚠ Только партнёр может подтвердить этим.", show_alert=True)
            return

        if deal['partner_confirmed']:
            await callback_query.answer("Вы уже подтвердили сделку.", show_alert=True)
            return

        deal['partner_confirmed'] = True

        # Отправляем партнёру сообщение — подождите пока владелец переведёт звёзды
        await callback_query.answer("Вы подтвердили сделку.")
        await bot.send_message(partner_id, "⏳ Подождите, пока владелец сделки переведёт вам звёзды.")

        # Отправляем владельцу кнопку подтвердить оплату (если её ещё нет)
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton(text="💸 Оплатить", callback_data=f"pay_{owner_id}"),
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_owner_{owner_id}")
        )
        await bot.send_message(owner_id, "Партнёр подтвердил сделку. Подтвердите оплату звёзд:", reply_markup=keyboard)


    elif data.startswith("pay_"):
        owner_id = int(data.split("_")[-1])
        if user_id != owner_id:
            await callback_query.answer("⚠ Только владелец сделки может нажать оплатить.", show_alert=True)
            return
        await callback_query.answer("Оплата пока не реализована.", show_alert=True)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
