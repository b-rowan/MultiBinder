from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, close_db

BASE_DIR = Path(__file__).parent

from app.routers import auth, cards, collections, decks, admin
from app.templates import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="MultiBinder",
    description="Magic: The Gathering Collection & Deck Tracker",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Include routers
app.include_router(auth.router, tags=["auth"])
app.include_router(cards.router, tags=["cards"])
app.include_router(collections.router, tags=["collections"])
app.include_router(decks.router, tags=["decks"])
app.include_router(admin.router, tags=["admin"])


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")
