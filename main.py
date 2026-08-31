from fastapi import FastAPI
from app.routers.auth import auth_router
from app.routers.product import product_router
from app.routers.orders import order_router
from app.routers.cart import cart_router
from app.routers.payments import payment_router

from contextlib import asynccontextmanager

from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Startup
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()


app = FastAPI(title="FastAPI Application")

app.include_router(
    router=auth_router, prefix="/users", tags=["Authentication routes for users"]
)
app.include_router(
    router=product_router, prefix="/products", tags=["Routes for products"]
)
app.include_router(router=order_router, prefix="/orders", tags=["Routes for orders"])
app.include_router(router=cart_router, prefix="/cart", tags=["Routes for cart entries"])
app.include_router(router=payment_router, prefix="/payments", tags=["Payment webhooks"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
