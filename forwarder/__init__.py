import logging
import json
from os import getenv, path
from typing import NamedTuple, Optional

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

load_dotenv(".env")

# Logging setup
logging.basicConfig(
    format="[ %(asctime)s: %(levelname)-8s ] %(name)-20s - %(message)s",
    level=logging.INFO,
)

LOGGER = logging.getLogger(__name__)

httpx_logger = logging.getLogger('httpx')
httpx_logger.setLevel(logging.WARNING)

class OutputSettings(NamedTuple):
    """Structure for output chat settings"""
    verification_chat_id: int
    verification_topic_id: Optional[int]
    enable_verification_messages: bool

def load_config():
    """Load and validate configuration"""
    config_name = "chat_list.json"
    if not path.isfile(config_name):
        LOGGER.error("No chat_list.json config file found! Exiting...")
        exit(1)
        
    with open(config_name, "r") as data:
        config = json.load(data)
    
    # Extract output settings
    output_config = config.get('output_settings', {})
    
    # Convert chat ID to int and handle optional topic ID
    try:
        verification_chat_id = int(output_config.get('verification_chat_id', 0))
        verification_topic_id = int(output_config.get('verification_topic_id', 0)) or None
        enable_messages = output_config.get('enable_verification_messages', True)
        
        if verification_chat_id == 0:
            LOGGER.warning("No verification chat ID configured!")
            
        OUTPUT_SETTINGS = OutputSettings(
            verification_chat_id=verification_chat_id,
            verification_topic_id=verification_topic_id,
            enable_verification_messages=enable_messages
        )
        
    except (ValueError, TypeError) as e:
        LOGGER.error(f"Invalid output settings configuration: {e}")
        OUTPUT_SETTINGS = OutputSettings(0, None, False)
    
    return config.get('forwarding_rules', []), OUTPUT_SETTINGS

# Load configuration
CONFIG, OUTPUT_SETTINGS = load_config()

# Bot token setup
BOT_TOKEN = getenv("BOT_TOKEN")
if not BOT_TOKEN:
    LOGGER.error("No BOT_TOKEN token provided!")
    exit(1)

OWNER_ID = int(getenv("OWNER_ID", "0"))
REMOVE_TAG = getenv("REMOVE_TAG", "False") in {"true", "True", 1}

# Create application builder with specific settings
application = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .concurrent_updates(True)
    .arbitrary_callback_data(True)
    .post_init(lambda app: LOGGER.info("Bot initialized successfully"))
    .post_shutdown(lambda app: LOGGER.info("Bot shutdown successfully"))
    .build()
)

def get_bot():
    """Get the bot instance"""
    return application