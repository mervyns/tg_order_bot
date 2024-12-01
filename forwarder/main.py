import asyncio
import importlib
import sys
from forwarder import LOGGER, get_bot
from forwarder.modules import ALL_MODULES
from forwarder.modules.initialize import initialize, get_db_manager
from telegram import Update

async def cleanup():
    """Cleanup resources"""
    try:
        # Cleanup database
        db_manager = await get_db_manager()
        if db_manager:
            await db_manager.close()
            LOGGER.info("Database connection closed")
    except Exception as e:
        LOGGER.error(f"Error during cleanup: {e}")

async def initialize_app():
    """Initialize all required components"""
    try:
        # Initialize database first
        LOGGER.info("Initializing database...")
        db_manager = await initialize()
        if not db_manager:
            LOGGER.error("Failed to initialize database")
            return False

        # Get the bot instance first
        LOGGER.info("Initializing bot...")
        bot = get_bot()
        await bot.initialize()

        # Load all modules
        LOGGER.info("Loading modules...")
        for module in ALL_MODULES:
            importlib.import_module("forwarder.modules." + module)
        
        LOGGER.info("Successfully loaded modules: " + str(ALL_MODULES))
        
        # Register handlers from all modules
        LOGGER.info("Registering handlers...")
        from forwarder.modules.message_handler import register_handlers as register_message_handlers
        from forwarder.modules.default import register_handlers as register_default_handlers
        from forwarder.modules.misc import register_handlers as register_misc_handlers
        
        register_message_handlers()
        register_default_handlers()
        register_misc_handlers()
        
        return True
        
    except Exception as e:
        LOGGER.error(f"Initialization failed: {e}")
        return False

async def main():
    """Main async function to run the bot"""
    try:
        # Run initialization
        if not await initialize_app():
            LOGGER.error("Initialization failed")
            return
            
        LOGGER.info("Starting bot...")
        
        # Get the bot instance
        bot = get_bot()
        
        # Run the bot until stopped
        LOGGER.info("Bot is running...")
        await bot.initialize()
        await bot.start()
        
        # Start polling in the background
        LOGGER.info("Starting polling...")
        await bot.updater.start_polling(drop_pending_updates=True)
        
        # Keep the bot running
        LOGGER.info("Bot is now polling for updates...")
        try:
            # Create a future that never completes
            running = asyncio.Event()
            await running.wait()
        except asyncio.CancelledError:
            LOGGER.info("Received shutdown signal")
            
    except Exception as e:
        LOGGER.error(f"Bot stopped due to error: {e}")
    finally:
        # Cleanup
        LOGGER.info("Cleaning up resources...")
        bot = get_bot()
        if bot.running:
            LOGGER.info("Stopping bot gracefully...")
            try:
                # Stop the updater first
                if bot.updater.running:
                    await bot.updater.stop()
                # Then stop and shutdown the bot
                await bot.stop()
                await bot.shutdown()
            except Exception as stop_error:
                LOGGER.error(f"Error stopping bot: {stop_error}")
        await cleanup()

def run():
    """Entry point function that runs the async main"""
    try:
        # Create new event loop and run main
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped by user")
    except Exception as e:
        LOGGER.error(f"Fatal error: {e}")
    finally:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.close()

if __name__ == "__main__":
    run()