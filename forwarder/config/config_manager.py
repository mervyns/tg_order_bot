# config_manager.py
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import asdict

from dotenv import load_dotenv

from forwarder import LOGGER
from forwarder.config.types import AppConfig, ChatConfig, DatabaseConfig, ForwardingRule, OutputConfig, OutputSettings, SanctionsConfig, ServiceConfig, TopicConfig
from forwarder.database.manager import DatabaseManager
from forwarder.utils.sheets_manager import GoogleSheetsManager
from forwarder.utils.swift import Swift

PACKAGE_DIR = Path(__file__).parent.parent  # Gets the forwarder package directory
CONFIG_DIR = PACKAGE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"
SERVICE_ACCOUNT_FILE = CONFIG_DIR / "hd-tg-gc.json"

# Ensure config directory exists
CONFIG_DIR.mkdir(exist_ok=True)


class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class ConfigManager:
    def __init__(self, config_dir: str, config_path: str, env_path: str = ".env"):
        LOGGER.info(f"Initializing ConfigManager with env_path: {env_path}")
        self.config_dir = config_dir
        self.config_path = config_path
        self.env_path = env_path
        
        # Load environment first
        self._load_environment(self.env_path)
        
        # Load config file
        self.config = self._load_config()

    def get_database_config(self) -> Optional[Dict[str, any]]:
        """Get database configuration from environment and config"""
        LOGGER.info("Getting database configuration")
        
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        LOGGER.info(f"Database URL from environment: {database_url}")
        
        # Debug: Print actual URL (sanitized for logging)
        if database_url:
            safe_url = database_url.split('@')[-1] if '@' in database_url else 'malformed'
            LOGGER.info(f"Database URL from environment (host part): {safe_url}")
        else:
            LOGGER.error("DATABASE_URL not found in environment variables")
            return None

        # Get additional database config from config file
        try:
            db_config = self.config.services.database if hasattr(self.config.services, 'database') else {}
            
            config = {
                'database_url': database_url,  # Use the URL from environment
                'pool_size': db_config.get('pool_size', 20),
                'max_overflow': db_config.get('max_overflow', 10),
                'pool_timeout': db_config.get('pool_timeout', 30),
                'health_check_interval': db_config.get('health_check_interval', 300)
            }
            
            LOGGER.info("Database configuration assembled:")
            LOGGER.info(f"Config (sanitized): {config}")
            
            return config
            
        except Exception as e:
            LOGGER.error(f"Error assembling database configuration: {e}")
            import traceback
            LOGGER.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _load_environment(self, env_path: str) -> None:
        """Load environment variables"""
        LOGGER.info(f"Loading environment from: {env_path}")
        
        if not os.path.exists(env_path):
            LOGGER.error(f"Environment file not found: {env_path}")
            raise ConfigurationError(f"Environment file not found: {env_path}")
            
        # Check .env file permissions
        try:
            with open(env_path, 'r') as f:
                env_content = f.read()
            LOGGER.debug(f"Successfully read .env file with content length: {len(env_content)}")
        except Exception as e:
            LOGGER.error(f"Error reading .env file: {e}")
            raise
            
        load_dotenv(env_path)
        LOGGER.debug("Environment variables loaded from .env file")

        # Validate required environment variables
        required_vars = ["BOT_TOKEN", "DATABASE_URL"]  # Added DATABASE_URL to required vars
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            LOGGER.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            raise ConfigurationError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _load_config(self) -> AppConfig:
        """Load and validate configuration file"""
        if not os.path.exists(self.config_path):
            raise ConfigurationError(f"Configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)

            # Add database configuration to services if it exists
            services_config = config_data.get("services", {})
            if "database" not in services_config:
                services_config["database"] = {
                    "pool_size": 20,
                    "max_overflow": 10,
                    "pool_timeout": 30,
                    "health_check_interval": 300
                }

            # Update the config data with database settings
            config_data["services"] = services_config

            service_account_file = config_data.get("services", {}).get("sheets_service_account", "")
            if service_account_file:
                service_account_path = self.config_dir / service_account_file
                if not service_account_path.exists():
                    raise ConfigurationError(f"Service account file not found: {service_account_path}")
                service_account_file = str(service_account_path)

            sanctions_config = None
            if 'sanctions' in config_data.get('services', {}):
                sanctions_data = config_data['services']['sanctions']
                sanctions_config = SanctionsConfig(
                    api_key=sanctions_data.get('api_key', ''),
                    api_base_url=sanctions_data.get('api_base_url', '')
                )

            # Load service configuration
            service_config = ServiceConfig(
                bot_token=os.getenv("BOT_TOKEN", ""),
                database=config_data.get("services", {}).get("database", {}),
                owner_id=int(os.getenv("OWNER_ID", "0")),
                remove_tag=os.getenv("REMOVE_TAG", "False").lower() in {"true", "1"},
                swift_api_key=config_data.get("services", {}).get("swift_api_key", ""),
                swift_api_url=config_data.get("services", {}).get("swift_api_url", ""),
                sheets_service_account=config_data.get("services", {}).get("sheets_service_account", ""),
                sanctions=sanctions_config
            )

            # Load output settings
            output_config = config_data.get("output_settings", {})
            output_settings = OutputSettings(
                verification_chat_id=int(output_config.get("verification_chat_id", 0)),
                verification_topic_id=int(output_config.get("verification_topic_id", 0)) or None,
                enable_verification_messages=output_config.get("enable_verification_messages", True)
            )

            # Load chat configurations
            chats = {}
            for chat_id, chat_data in config_data.get("chats", {}).items():
                topics = {}
                for topic_id, topic_data in chat_data.get("topics", {}).items():
                    topics[int(topic_id)] = TopicConfig(
                        id=int(topic_id),
                        type=topic_data["type"],
                        sheet_configs=topic_data.get("sheet_configs", {}),
                        validation_rules=topic_data.get("validation_rules", {})
                    )
                chats[int(chat_id)] = ChatConfig(
                    chat_id=int(chat_id),
                    topics=topics
                )

            return AppConfig(
                services=service_config,
                chats=chats,
                output_settings=output_settings,
                forwarding_rules=config_data.get("forwarding_rules", [])
            )

        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
        except (ValueError, TypeError) as e:
            raise ConfigurationError(f"Invalid configuration values: {e}")

    @property
    def services(self) -> ServiceConfig:
        return self.config.services

    @property
    def output_settings(self) -> OutputSettings:
        return self.config.output_settings

    @property
    def forwarding_rules(self) -> List[dict]:
        return self.config.forwarding_rules

    def get_topic_config(self, chat_id: int, topic_id: int) -> Optional[TopicConfig]:
        """Get configuration for a specific topic in a chat"""
        chat_config = self.config.chats.get(chat_id)
        if chat_config:
            return chat_config.topics.get(topic_id)
        return None
    
    def get_chat_ids(self) -> List[int]:
        """Get list of configured chat IDs"""
        return list(self.config.chats.keys())

    def get_sheet_managers(self, chat_id: int, topic_id: int) -> Dict[str, GoogleSheetsManager]:
        """Get sheet managers for a specific topic"""
        topic_config = self.get_topic_config(chat_id, topic_id)
        if not topic_config:
            return {}
        
        # Get service account file path relative to config directory
        service_account_file = self.config.services.sheets_service_account
        service_account_path = self.config_dir / service_account_file
        
        if not service_account_path.exists():
            raise ConfigurationError(f"Service account file not found: {service_account_path}")
        
        return {
            sheet_name: GoogleSheetsManager(
                str(service_account_path),
                sheet_id
            )
            for sheet_name, sheet_id in topic_config.sheet_configs.items()
        }

    def get_sanctions_config(self) -> Optional[Dict[str, str]]:
        """Get sanctions config as a dictionary if it exists"""
        if self.config.services.sanctions:
            return {
                'api_key': self.config.services.sanctions.api_key,
                'api_base_url': self.config.services.sanctions.api_base_url
            }
        return None

    def get_swift_verifier(self) -> Swift:
        """Get Swift verifier instance"""
        return Swift(
            api_key=self.config.services.swift_api_key,
            api_url=self.config.services.swift_api_url
        )
    
def initialize_database(config_manager: ConfigManager) -> Optional[DatabaseManager]:
    """Initialize database with proper error handling and logging"""
    LOGGER.info("Initializing database...")
    
    try:
        db_config = config_manager.get_database_config()
        if not db_config:
            LOGGER.error("Failed to get database configuration")
            return None
            
        LOGGER.info("Got database configuration, initializing manager...")
        return DatabaseManager.initialize(**db_config)
        
    except Exception as e:
        LOGGER.error(f"Failed to initialize database: {e}")
        import traceback
        LOGGER.error(f"Traceback: {traceback.format_exc()}")
        return None

config_manager = ConfigManager(
    config_dir=CONFIG_DIR,
    config_path=CONFIG_FILE,
    env_path=PACKAGE_DIR.parent / ".env"
)

# Export the singleton instance
def get_config() -> ConfigManager:
    return config_manager