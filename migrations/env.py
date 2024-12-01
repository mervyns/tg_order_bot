# migrations/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root directory to Python path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Load environment variables before importing models
env_path = root_dir / '.env'
load_dotenv(env_path, override=True)

from forwarder.database.base import Base
from forwarder.database.models import User, Order, AuditLog

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = Base.metadata

def get_url():
    """Get database URL from environment"""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL not found in environment")

    return url

# Override sqlalchemy.url in alembic.ini
config.set_main_option("sqlalchemy.url", get_url())

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,  # Make sure this is set
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,  # Make sure this is set
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()