import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from init_db import init_db
from telegram_bot import bot_runner
from routes.items import router as items_router
from routes.categories import router as categories_router
from routes.settings import router as settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("grocery_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database is initialized
    logger.info("Initializing database...")
    init_db()

    # Start Telegram background bot polling
    logger.info("Starting Telegram bot background worker...")
    bot_runner.start()

    yield

    # Shutdown: Stop Telegram bot
    logger.info("Stopping Telegram bot...")
    bot_runner.stop()

app = FastAPI(
    title="Smart Grocery List API",
    description="Containerized Grocery List API with Hebrew AI classification and Telegram integration",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(items_router)
app.include_router(categories_router)
app.include_router(settings_router)

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Smart Grocery List"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
