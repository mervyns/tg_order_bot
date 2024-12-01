import asyncio
import os
from pathlib import Path
import aiohttp
import re
from typing import Union, Optional, Dict

from telegram import Update, Message, MessageId
from telegram.ext import MessageHandler, filters, ContextTypes
from forwarder.config.config_manager import get_config
from forwarder.utils.order import OrderProcessor
from forwarder.utils.swift import Swift
from forwarder.modules.initialize import get_initialized_db

from forwarder import REMOVE_TAG, LOGGER, get_bot, OUTPUT_SETTINGS

# Initialize configuration manager
config_manager = get_config()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Add these constants at the top with your other configurations
SHEETS_SERVICE_ACCOUNT_FILE = os.path.join(BASE_DIR, "hd-tg-gc.json")
# # Create multiple sheet managers
# sheets_managers = {
#     sheet_name: GoogleSheetsManager(SHEETS_SERVICE_ACCOUNT_FILE, sheet_id)
#     for sheet_name, sheet_id in SPREADSHEET_IDS.items()
# }

# Configuration
SWIFT_API_KEY = "sk_0b92681192307a1b0dee01e76a18325908e856a8e61e0ed905fe11ee87e2574e"
SWIFT_API_URL = "https://swiftcodesapi.com/v1/swifts"
swift_verifier = Swift(
    api_key=SWIFT_API_KEY,
    api_url=SWIFT_API_URL
)

async def send_message(
    message: Message, chat_id: int, thread_id: Optional[int] = None
) -> Union[MessageId, Message]:
    if REMOVE_TAG:
        return await message.copy(chat_id, message_thread_id=thread_id)  # type: ignore
    return await message.forward(chat_id, message_thread_id=thread_id)  # type: ignore

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    message = update.effective_message
    if not message or not message.text:
        return

    chat_id = message.chat_id
    topic_id = message.message_thread_id
    
    try:
        topic_config = config_manager.get_topic_config(chat_id, topic_id)
        if not topic_config:
            LOGGER.info(f"No configuration found for chat {chat_id}, topic {topic_id}")
            return
            
        sheet_managers = config_manager.get_sheet_managers(chat_id, topic_id)
        swift_verifier = config_manager.get_swift_verifier()

        sanctions_config = config_manager.get_sanctions_config()
        # Get database manager instance
        db_manager = await asyncio.wait_for(
            get_initialized_db(),
            timeout=10.0  # 10 second timeout
        )
        if not db_manager:
            LOGGER.error("Failed to get database manager")
            return
            
        """Handle incoming messages"""
        if topic_config.type == "order":
            processor = OrderProcessor(
                sheets_managers=sheet_managers,
                swift_verifier=swift_verifier,
                order_topic_id=topic_id,
                db_manager=db_manager,
                validation_rules=topic_config.validation_rules,
                sanctions_config=sanctions_config if topic_config.validation_rules.get('check_sanctions') else None
            )
            try:
                async with asyncio.timeout(60):  # Increased from 30 to 60 seconds
                    await processor.process_order(update, context)
            except asyncio.TimeoutError:
                LOGGER.error("Order processing timed out")
                if context and update.effective_message:
                    await context.bot.send_message(
                        chat_id=OUTPUT_SETTINGS.verification_chat_id,
                        message_thread_id=OUTPUT_SETTINGS.verification_topic_id,
                        text="❌ Order processing timed out. Please check."
                    )
            except Exception as e:
                LOGGER.error(f"Error processing order: {e}")
                if context and update.effective_message:
                    await context.bot.send_message(
                        chat_id=OUTPUT_SETTINGS.verification_chat_id,
                        message_thread_id=OUTPUT_SETTINGS.verification_topic_id,
                        text="❌ Error processing order. Please check."
                    )
    except Exception as e:
        LOGGER.error(f"Error in message handler: {e}")
        if context and update.effective_message:
            await context.bot.send_message(
                chat_id=OUTPUT_SETTINGS.verification_chat_id,
                message_thread_id=OUTPUT_SETTINGS.verification_topic_id,
                text="❌ An error occurred. Please check."
            )

# Register handler
MESSAGE_HANDLER = MessageHandler(
    filters.Chat([int(chat_id) for chat_id in config_manager.config.chats.keys()])
    & ~filters.COMMAND
    & ~filters.StatusUpdate.ALL,
    message_handler,
)

def register_handlers():
    """Register message handlers with the bot"""
    bot = get_bot()
    bot.add_handler(MESSAGE_HANDLER)