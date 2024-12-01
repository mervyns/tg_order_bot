# config_types.py
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class SanctionsConfig:
    api_key: str
    api_base_url: str

@dataclass
class ValidationRules:
    check_swift: bool
    check_iban: bool
    check_sanctions: bool  # New flag for sanctions check

@dataclass
class TopicConfig:
    id: int
    type: str  # e.g., "order", "payment", etc.
    sheet_configs: Dict[str, str]  # sheet_name -> sheet_id mapping
    validation_rules: ValidationRules

@dataclass
class ChatConfig:
    chat_id: int
    topics: Dict[int, TopicConfig]

@dataclass
class DatabaseConfig:
    url: str
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    health_check_interval: int = 300

@dataclass
class ServiceConfig:
    bot_token: str
    database: DatabaseConfig
    owner_id: int
    remove_tag: bool
    swift_api_key: str
    swift_api_url: str
    sheets_service_account: str
    sanctions: Optional[SanctionsConfig] = None

@dataclass
class OutputSettings:
    verification_chat_id: int
    verification_topic_id: Optional[int]
    enable_verification_messages: bool

@dataclass
class OutputConfig:
    verification_chat_id: int
    verification_topic_id: int
    enable_verification_messages: bool

@dataclass
class ForwardingRule:
    source: str
    destination: List[str]

@dataclass
class AppConfig:
    chats: Dict[int, ChatConfig]
    services: ServiceConfig
    output_settings: OutputConfig
    forwarding_rules: List[ForwardingRule]