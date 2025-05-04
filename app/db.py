# from fastapi import FastAPI
# from tortoise.contrib.fastapi import register_tortoise
# from contextlib import asynccontextmanager
# from .config import TORTOISE_ORM_CONFIG, settings # Import config
# import logging

# log = logging.getLogger("uvicorn")

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     log.info("Initializing Tortoise ORM...")
#     try:
#         register_tortoise(
#             app,
#             config=TORTOISE_ORM_CONFIG,
#             generate_schemas=False,
#             add_exception_handlers=True,
#         )
#         log.info("Tortoise ORM initialized successfully.")
#     except Exception as e:
#         log.error(f"Failed to initialize Tortoise ORM: {e}", exc_info=True)
#     yield
#     log.info("Shutting down Tortoise ORM connections.")

# app/db.py

# from fastapi import FastAPI
# from tortoise.contrib.fastapi import register_tortoise
# from contextlib import asynccontextmanager
# from .config import TORTOISE_ORM_CONFIG, settings # Import config
# import logging
# from tortoise import Tortoise, connections # Import Tortoise and connections

# # Use uvicorn's logger or configure your own
# log = logging.getLogger("uvicorn")

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     log.info("--- Starting application lifespan ---")
#     log.info("Attempting to initialize Tortoise ORM...")
#     try:
#         # This function should configure Tortoise ORM connections
#         register_tortoise(
#             app,
#             config=TORTOISE_ORM_CONFIG,
#             generate_schemas=False, # We use Aerich for migrations
#             add_exception_handlers=True,
#         )
#         log.info("Tortoise ORM registration called.")

#         # --- Explicitly check if the connection was created ---
#         log.info("Checking for 'default' connection after registration...")
#         # connections.get will raise KeyError if 'default' doesn't exist
#         default_conn = connections.get("default")
#         log.info(f"Successfully retrieved 'default' connection: {default_conn}")

#         # --- Optional: Test the connection ---
#         log.info("Attempting a simple test query on 'default' connection...")
#         await default_conn.execute_query("SELECT 1")
#         log.info("Test query executed successfully.")
#         # --- End Optional Test ---

#         log.info("--- Tortoise ORM initialization appears successful ---")

#     except KeyError:
#         log.error("!!! CRITICAL: 'default' connection key not found after register_tortoise. Check TORTOISE_ORM_CONFIG.", exc_info=True)
#     except Exception as e:
#         log.error(f"!!! CRITICAL: Failed during Tortoise ORM initialization or test query: {e}", exc_info=True)
#         # Optionally re-raise to prevent app startup if DB init fails critically
#         # raise RuntimeError("Database initialization failed") from e

#     yield # Application runs here

#     # --- Shutdown ---
#     log.info("--- Starting application shutdown ---")
#     log.info("Closing Tortoise ORM connections (managed by register_tortoise)...")
#     # register_tortoise handles shutdown, but we log that we reached this point
#     log.info("--- Application lifespan ended ---")


# app/db.py

from fastapi import FastAPI
# Removed: from tortoise.contrib.fastapi import register_tortoise
from contextlib import asynccontextmanager
from .config import TORTOISE_ORM_CONFIG, settings # Import config
import logging
from tortoise import Tortoise, connections # Import Tortoise and connections

# Use uvicorn's logger or configure your own
log = logging.getLogger("uvicorn")

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("--- Starting application lifespan ---")
    log.info("Attempting EXPLICIT Tortoise ORM initialization...")
    try:
        await Tortoise.init(
            config=TORTOISE_ORM_CONFIG
        )
        log.info("Tortoise.init() called.")

        # --- Check if the connection was created ---
        log.info("Checking for 'default' connection after Tortoise.init()...")
        default_conn = connections.get("default")
        log.info(f"Successfully retrieved 'default' connection: {default_conn}")

        # --- Optional: Test the connection ---
        log.info("Attempting a simple test query on 'default' connection...")
        await default_conn.execute_query("SELECT 1") # Simple query to test
        log.info("Test query executed successfully.")
        # --- End Optional Test ---

        log.info("--- Tortoise ORM initialization appears successful ---")

    except KeyError:
        log.error("!!! CRITICAL: 'default' connection key not found after Tortoise.init(). Check TORTOISE_ORM_CONFIG.", exc_info=True)
    except Exception as e:
        log.error(f"!!! CRITICAL: Failed during Tortoise ORM initialization or test query: {e}", exc_info=True)

    yield 

    # --- Shutdown ---
    log.info("--- Starting application shutdown ---")
    log.info("Closing Tortoise ORM connections explicitly...")
    try:
        await Tortoise.close_connections()
        log.info("Tortoise connections closed successfully.")
    except Exception as e:
        log.error(f"Error closing Tortoise connections: {e}", exc_info=True)
    log.info("--- Application lifespan ended ---")

