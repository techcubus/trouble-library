from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, db
from app.admin.queue import router as queue_router
from app.admin.routes import router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="trouble-library admin")


@app.on_event("startup")
def on_startup() -> None:
    config.ensure_directories()
    db.init_db()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(router)
app.include_router(queue_router)
