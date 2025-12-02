from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models
from app.config import get_settings
from app.database import Base, engine
from app.routers import tracked_products
from app.services.notifier import EmailNotifier
from app.services.scheduler import PriceCheckScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
notifier = EmailNotifier(settings)
scheduler = PriceCheckScheduler(settings=settings, notifier=notifier)


@asynccontextmanager
def lifespan(app: FastAPI):
    logger.info("Ensuring database tables exist")
    Base.metadata.create_all(bind=engine)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Price Tracker", lifespan=lifespan)
app.include_router(tracked_products.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
