from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_allowed_origins
from app.db import client, db
from app.items import router as items_router
from app.pdf import router as pdf_router
from app.resource import router as resource_router


@asynccontextmanager
async def lifespan(_: FastAPI):
	yield
	client.close()


app = FastAPI(title="root-cause API", lifespan=lifespan)

# CORS is a safety net for direct (non-proxied) browser calls, e.g. from another
# frontend or during testing. The deployed Svelte app reaches the API same-origin
# through the /api/* proxy, so this is normally never exercised. Set
# ALLOWED_ORIGINS (comma-separated) in the environment to allow direct calls.
if origins := get_allowed_origins():
	app.add_middleware(
		CORSMiddleware,
		allow_origins=origins,
		allow_methods=["*"],
		allow_headers=["*"],
	)

app.include_router(items_router, prefix="/api")
app.include_router(pdf_router, prefix="/api")
app.include_router(resource_router, prefix="/api")


@app.get("/health")
async def health():
	try:
		await db.command("ping")
	except Exception:
		return {"status": "error", "db": "unreachable"}
	return {"status": "ok"}
