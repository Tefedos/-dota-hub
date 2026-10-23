from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.services import (
    InvalidMatchId,
    JobService,
    RequestStatus,
    mini_app_deep_link,
    parse_match_id,
)
from app.core.config import Settings

PRIVATE_HELP = (
    "Dota Hub работает в группах. Добавьте бота в группу и отправьте /match <match_id>. "
    "Match ID можно найти в истории игр Dota 2."
)
GROUP_HELP = "Команда: /match <match_id>. Бот загрузит данные матча из OpenDota и сообщит результат."
BAD_MATCH_ID = "Укажите Match ID как положительное целое число: /match 123456789."
GROUP_NOT_ALLOWED = "Команда /match не включена для этой группы."


def create_router(settings: Settings, jobs: JobService) -> Router:
    router = Router(name="dota-hub-group-bot")
    allowed = frozenset(settings.telegram_allowed_chat_ids)

    @router.message(Command("start", "help"))
    async def help_command(message: Message) -> None:
        await message.answer(PRIVATE_HELP if message.chat.type == ChatType.PRIVATE else GROUP_HELP, parse_mode=None)

    @router.message(Command("match"))
    async def match_command(message: Message, command: CommandObject) -> None:
        if message.chat.type == ChatType.PRIVATE:
            await message.answer(PRIVATE_HELP, parse_mode=None)
            return
        if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return
        if message.chat.id not in allowed:
            await message.answer(GROUP_NOT_ALLOWED, parse_mode=None)
            return
        try:
            match_id = parse_match_id(command.args)
        except InvalidMatchId:
            await message.answer(BAD_MATCH_ID, parse_mode=None)
            return
        if message.from_user is None:
            await message.answer("Не удалось определить отправителя команды.", parse_mode=None)
            return
        result = jobs.reserve_request(match_id, message.from_user.id, message.chat.id)
        if result.status == RequestStatus.COOLDOWN:
            await message.answer(f"Слишком частые запросы. Повторите через {result.retry_after_seconds} сек.", parse_mode=None)
        else:
            await message.answer(f"Match ID {match_id} принят. Загружаю данные из OpenDota…", parse_mode=None)

            async def notify(text: str) -> None:
                username = settings.bot_username
                if username is None and message.bot is not None:
                    username = (await message.bot.me()).username
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text='Подробный анализ', url=mini_app_deep_link(username, match_id),
                )]]) if username else None
                await message.answer(text[:3500], parse_mode=None, reply_markup=keyboard)

            jobs.start_request(match_id, notify)

    return router
