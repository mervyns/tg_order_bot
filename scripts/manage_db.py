# scripts/manage_db.py
import click
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

# Set the project root directory
ROOT_DIR = Path(__file__).parent.parent

# Load environment variables
load_dotenv(ROOT_DIR / '.env')

def ensure_env():
    """Ensure required environment variables are set"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise click.ClickException(
            'DATABASE_URL environment variable is not set. '
            'Please set it in your .env file or environment.'
        )

@click.group()
def cli():
    """Database management commands."""
    ensure_env()
    pass

@cli.command()
def init():
    """Initialize Alembic migrations."""
    click.echo("Initializing Alembic migrations...")
    subprocess.run(["poetry", "run", "alembic", "init", "migrations"], cwd=ROOT_DIR)

@cli.command()
@click.option('--message', '-m', required=True, help='Migration message')
def migrate(message):
    """Create a new migration."""
    click.echo(f"Creating new migration: {message}")
    subprocess.run(["poetry", "run", "alembic", "revision", "--autogenerate", "-m", message], cwd=ROOT_DIR)

@cli.command()
@click.option('--revision', '-r', default='head', help='Revision to upgrade to')
def upgrade(revision):
    """Upgrade database to a later version."""
    click.echo(f"Upgrading database to: {revision}")
    subprocess.run(["poetry", "run", "alembic", "upgrade", revision], cwd=ROOT_DIR)

@cli.command()
@click.option('--revision', '-r', help='Revision to downgrade to')
def downgrade(revision):
    """Revert database to a previous version."""
    if not revision:
        click.echo("Please specify a revision to downgrade to")
        return
    click.echo(f"Downgrading database to: {revision}")
    subprocess.run(["poetry", "run", "alembic", "downgrade", revision], cwd=ROOT_DIR)

@cli.command()
def history():
    """Show migration history."""
    click.echo("Migration history:")
    subprocess.run(["poetry", "run", "alembic", "history"], cwd=ROOT_DIR)

@cli.command()
def current():
    """Show current revision."""
    click.echo("Current revision:")
    subprocess.run(["poetry", "run", "alembic", "current"], cwd=ROOT_DIR)

if __name__ == '__main__':
    cli()