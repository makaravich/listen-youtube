"""Telegram bot: send a YouTube link, get the audio back. Long polling."""
import asyncio
import html
import logging
import shutil
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, FSInputFile, Message

from . import audio
from .config import load

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("listen_youtube")

cfg = load()
dp = Dispatcher()
# One job at a time: it's a personal bot and ffmpeg/uploads are the bottleneck anyway.
job_lock = asyncio.Lock()


def allowed(message: Message) -> bool:
    return not cfg.allowed_ids or (message.from_user and message.from_user.id in cfg.allowed_ids)


def fmt_duration(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dp.message(CommandStart())
async def start(message: Message) -> None:
    if not allowed(message):
        await message.answer(f"Это личный бот. Твой id: {message.from_user.id}")
        return
    await message.answer("Пришли ссылку на YouTube-видео — верну звук.\n/check — проверить cookies YouTube.")


CHECK_TZ = ZoneInfo("Europe/Warsaw")
CHECK_HOUR = 10


async def run_check() -> tuple[bool, str]:
    # Under the job lock: yt-dlp rewrites the cookie file, don't race a running download.
    async with job_lock:
        return await asyncio.to_thread(audio.check_access, cfg)


@dp.message(Command("check"))
async def check(message: Message) -> None:
    if not allowed(message):
        return
    status = await message.reply("Проверяю cookies…")
    ok, verdict = await run_check()
    await status.edit_text(("✅ " if ok else "❌ ") + verdict)


async def daily_cookie_check(bot: Bot) -> None:
    """Every day at CHECK_HOUR (Warsaw): warn the owners if YouTube stopped accepting the cookies."""
    while True:
        now = datetime.now(CHECK_TZ)
        nxt = now.replace(hour=CHECK_HOUR, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        await asyncio.sleep((nxt - now).total_seconds())
        try:
            ok, verdict = await run_check()
        except Exception:
            log.exception("daily cookie check crashed")
            ok, verdict = False, "Ежедневная проверка cookies упала, подробности в логе."
        log.info("daily cookie check: ok=%s %s", ok, verdict)
        if ok:
            continue
        for uid in cfg.allowed_ids:
            try:
                await bot.send_message(uid, f"⚠️ {verdict}\nПосле выгрузки — /check.")
            except TelegramAPIError as e:
                log.warning("cannot notify %s: %s", uid, e)


class Status:
    """Progress message; edits are cosmetic and must never break the job."""

    def __init__(self, message: Message):
        self.message = message
        self.text = message.text

    async def set(self, text: str) -> None:
        if text == self.text:
            return
        try:
            await self.message.edit_text(text)
            self.text = text
        except TelegramAPIError as e:
            log.warning("status edit failed: %s", e)

    async def follow(self, latest: dict, every: float = 2.0) -> None:
        """Mirror latest["text"] into the message; Telegram tolerates ~1 edit/s per chat, stay well below."""
        while True:
            await asyncio.sleep(every)
            await self.set(latest["text"])

    async def delete(self) -> None:
        try:
            await self.message.delete()
        except TelegramAPIError as e:
            log.warning("status delete failed: %s", e)


@dp.message(F.text | F.caption)
async def on_link(message: Message, bot: Bot) -> None:
    if not allowed(message):
        return
    url = audio.find_url(message.text or message.caption or "")
    if not url:
        await message.answer("Не вижу ссылки на YouTube.")
        return

    status = Status(await message.reply("В очереди…" if job_lock.locked() else "Получаю данные о видео…"))
    async with job_lock:
        await status.set("Получаю данные о видео…")
        work = cfg.work_dir / uuid.uuid4().hex
        try:
            # The worker thread only writes the latest line; the ticker edits the message at a safe rate.
            latest = {"text": "Получаю данные о видео…"}
            ticker = asyncio.create_task(status.follow(latest))
            try:
                res = await asyncio.to_thread(audio.download, cfg, url, work, lambda t: latest.__setitem__("text", t))
            finally:
                ticker.cancel()
            await status.set(f"{res.title}\nОтправляю…")
            thumb = FSInputFile(res.thumbnail) if res.thumbnail else None
            total = len(res.parts)
            for i, part in enumerate(res.parts, 1):
                suffix = f" ({i}/{total})" if total > 1 else ""
                if total > 1:
                    await status.set(f"{res.title}\nОтправляю часть {i}/{total}…")
                caption = f'<a href="{html.escape(res.url)}">{html.escape(res.title)}</a>{suffix}\n{fmt_duration(res.duration)}'
                if res.bitrate_kbps:
                    caption += f" · {res.bitrate_kbps} kbps"
                await bot.send_audio(
                    message.chat.id,
                    FSInputFile(part, filename=f"{res.title[:60].replace('/', '_')}{suffix}.m4a"),
                    caption=caption,
                    title=res.title + suffix,
                    performer=res.uploader or None,
                    duration=res.duration if total == 1 else None,
                    thumbnail=thumb,
                    reply_to_message_id=message.message_id,
                    request_timeout=600,
                )
            await status.delete()
        except audio.DownloadError as e:
            await status.set(f"❌ {e}")
        except Exception:
            log.exception("failed on %s", url)
            await status.set("❌ Что-то сломалось, подробности в логе.")
        finally:
            shutil.rmtree(work, ignore_errors=True)


async def main() -> None:
    # Leftovers from a crash/restart.
    for d in cfg.work_dir.iterdir():
        shutil.rmtree(d, ignore_errors=True)
    if cfg.cookies_file:
        log.info("using cookies: %s", cfg.cookies_file)
    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        await bot.set_my_commands([
            BotCommand(command="check", description="Проверить cookies YouTube"),
            BotCommand(command="start", description="Как пользоваться"),
        ])
    except TelegramAPIError as e:
        log.warning("set_my_commands failed: %s", e)
    checker = asyncio.create_task(daily_cookie_check(bot))
    try:
        await dp.start_polling(bot)
    finally:
        checker.cancel()


if __name__ == "__main__":
    asyncio.run(main())
