import os
import logging
import asyncio
from collections import deque
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

waiting = deque()
partners = {}
banned = set()
reports = 0
lock = asyncio.Lock()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать в Анонимку!\n\n"
        "🎭 Здесь ты можешь общаться анонимно.\n\n"
        "🔎 /search — найти собеседника\n"
        "⏭ /next — следующий собеседник\n"
        "🛑 /stop — закончить разговор\n"
        "🚨 /report — пожаловаться"
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    if user in banned:
        return await update.message.reply_text("🚫 Ты заблокирован.")

    async with lock:
        if user in partners:
            return await update.message.reply_text(
                "Ты уже общаешься! Используй /next."
            )

        if user in waiting:
            return await update.message.reply_text(
                "🔎 Ищем тебе собеседника..."
            )

        while waiting:
            partner = waiting.popleft()

            if partner != user and partner not in banned:
                partners[user] = partner
                partners[partner] = user

                await context.bot.send_message(
                    partner, "❤️ Собеседник найден! Можете общаться."
                )
                await update.message.reply_text(
                    "❤️ Собеседник найден! Можете общаться."
                )
                return

        waiting.append(user)

    await update.message.reply_text(
        "🔎 Ищем собеседника. Подожди немного..."
    )


async def stop_chat(user, context):
    partner = partners.pop(user, None)

    if partner:
        partners.pop(partner, None)
        await context.bot.send_message(
            partner, "🛑 Собеседник завершил разговор."
        )

    if user in waiting:
        waiting.remove(user)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    async with lock:
        await stop_chat(user, context)

    await update.message.reply_text("🛑 Диалог завершён.")


async def next_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop(update, context)
    await search(update, context)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global reports
    reports += 1

    user = update.effective_user.id

    if user not in partners:
        return await update.message.reply_text(
            "Сначала найди собеседника."
        )

    partner = partners[user]

    if ADMIN_ID:
        await context.bot.send_message(
            ADMIN_ID,
            f"🚨 Жалоба!\nОт пользователя: {user}\n"
            f"На пользователя: {partner}\n"
            f"Причина: {' '.join(context.args) or 'Не указана'}"
        )

    await update.message.reply_text(
        "✅ Жалоба отправлена администратору."
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"👑 Панель владельца\n\n"
        f"Ожидают: {len(waiting)}\n"
        f"Активных диалогов: {len(partners) // 2}\n"
        f"Жалоб: {reports}\n"
        f"Заблокировано: {len(banned)}"
    )


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return await update.message.reply_text(
            "Использование: /ban ID"
        )

    user = int(context.args[0])
    banned.add(user)

    async with lock:
        await stop_chat(user, context)

    await update.message.reply_text("🚫 Пользователь заблокирован.")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        return await update.message.reply_text(
            "Использование: /unban ID"
        )

    banned.discard(int(context.args[0]))
    await update.message.reply_text("✅ Разблокирован.")


async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    if user in banned:
        return

    partner = partners.get(user)

    if not partner:
        return await update.message.reply_text(
            "Сначала найди собеседника командой /search."
        )

    try:
        await context.bot.copy_message(
            chat_id=partner,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
    except Exception:
        await update.message.reply_text(
            "Не удалось отправить сообщение."
        )


def main():
    if not TOKEN or not ADMIN_ID:
        raise RuntimeError("Укажи BOT_TOKEN и ADMIN_ID!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("next", next_user))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))

    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, relay)
    )

    print("Anonimka is running!")
    app.run_polling()


if __name__ == "__main__":
    main()
