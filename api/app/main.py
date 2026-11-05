from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import client, db_name, target
from app.items import router as items_router


@asynccontextmanager
async def lifespan(_: FastAPI):
	yield
	client.close()


app = FastAPI(title="root-cause API", lifespan=lifespan)

app.include_router(items_router, prefix="/api")


@app.get("/health")
async def health():
	return {"status": "ok", "db": {"target": target, "name": db_name}}
