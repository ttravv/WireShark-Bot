from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
import logging
import asyncio
from aiogram.fsm.storage.memory import MemoryStorage
from tg_bot.config import load_config
import pyshark
import nest_asyncio

nest_asyncio.apply()


router = Router()
config = load_config(path=".env")
logger = logging.getLogger(__name__)

capture = None
capturing = False
current_interface = ""


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Используйте /start_capture <interface> для начала захвата трафика и /stop_capture для остановки."
    )


@router.message(Command("start_capture"))
async def cmd_start_capture(message: types.Message):
    global capturing, current_interface
    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "Пожалуйста, укажите интерфейс для захвата, например: /start_capture en0"
        )
        return

    interface = args[1]

    try:
        available_interfaces = pyshark.LiveCapture().interfaces

        if interface not in available_interfaces:
            await message.answer(
                f"Интерфейс '{interface}' не найден. Доступные интерфейсы: {', '.join(available_interfaces)}"
            )
            return

        capturing = True
        current_interface = interface
        await message.answer(f"Начинаю захват трафика на интерфейсе: {interface}")

        asyncio.create_task(capture_traffic(message.chat.id, interface))

    except Exception as e:

        await message.answer(f"Произошла ошибка: {e}")


@router.message(Command("stop_capture"))
async def cmd_stop_capture(message: types.Message):
    global capturing
    if capturing:
        capturing = False
        await message.answer("Захват трафика остановлен.")
    else:
        await message.answer("Захват не запущен.")


async def capture_traffic(chat_id, interface):
    global capture, capturing
    try:
        capture = pyshark.LiveCapture(interface=interface, display_filter="ip")

        await bot.send_message(chat_id, "Захват трафика запущен. Ожидание пакетов...")

        for packet in capture.sniff_continuously():
            if not capturing:
                break

            if "ip" in packet:
                src = packet.ip.src
                dst = packet.ip.dst
                protocol = packet.transport_layer
                message = (
                    f"Пакет: Source: {src}, Destination: {dst}, Protocol: {protocol}"
                )
                await bot.send_message(chat_id, message)

    except Exception as e:
        await bot.send_message(chat_id, f"Произошла ошибка: {e}")
    finally:
        capturing = False
        if capture:
            capture.close()


@router.message(Command("interfaces"))
async def list_interfaces(message: types.Message):
    try:
        interfaces = pyshark.tshark.tshark.get_tshark_interfaces()
        interface_list = "\n".join(interfaces)
        await message.reply(f"Доступные интерфейсы:\n{interface_list}")
    except Exception as e:
        await message.reply(f"Ошибка при получении интерфейсов: {e}")


async def main():
    global bot
    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s",
    )

    bot = Bot(token=config.tg_bot.token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("БОТ ОСТАНОВИЛСЯ")
