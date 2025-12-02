from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import tracked_products
from app.services.notifier import EmailNotifier
from app.services.scheduler import PriceCheckScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
notifier = EmailNotifier(settings)
scheduler = PriceCheckScheduler(settings=settings, notifier=notifier)
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
def lifespan(app: FastAPI):
    logger.info("Ensuring database tables exist")
    Base.metadata.create_all(bind=engine)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Price Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(tracked_products.router)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.TrackedProduct).order_by(models.TrackedProduct.created_at.desc()).all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "products": products})


@app.get("/health")
def health_check():
    return {"status": "ok"}
