import json
from aio_pika import DeliveryMode, Message
from fastapi import Body, FastAPI, APIRouter, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uuid
from datetime import datetime
from fastapi import Depends
from redis import Redis
import redis
from aio_pika.abc import AbstractRobustConnection

try:
    from models import CoffeeSize, CoffeeType, IngredientType, OrderCreate, OrderItem, OrderResponse, OrderStatus
except ImportError:
    from order_service.app.models import CoffeeSize, CoffeeType, IngredientType, OrderCreate, OrderItem, OrderResponse, OrderStatus
try:
    from order_service.app.redis_client import get_redis, get_rabbitmq_connection
except ImportError:
    from redis_client import get_redis, get_rabbitmq_connection

import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="order_service/templates")
router = APIRouter()

INGREDIENTS_INVENTORY = {
    "молоко": {"total": 10000, "reserved": 0},
    "кофе": {"total": 5000, "reserved": 0},
    "вода": {"total": 20000, "reserved": 0},
    "сироп": {"total": 3000, "reserved": 0},
    "пенка": {"total": 5000, "reserved": 0}
}

COFFEE_RECIPES = {
    "latte": {
        "молоко": 200,
        "кофе": 18,
        "пенка": 50
    },
    "americano": {
        "вода": 150,
        "кофе": 15
    },
    "cappuccino": {
        "молоко": 100,
        "кофе": 18,
        "пенка": 100
    },
    "espresso": {
        "кофе": 7,
        "вода": 30
    }
}

@router.get("/", response_class=HTMLResponse)
async def order_page(request: Request):
    return templates.TemplateResponse("make_order.html", {"request": request})

@router.post("/make_order", response_class=HTMLResponse)
async def make_order(
    request: Request,
    customer_name: str = Form(...),
    coffee_type: str = Form(...),
    coffee_size: str = Form(...),
    quantity: int = Form(1, gt=0, le=10),
    redis: Redis = Depends(get_redis),
    rabbit_conn: AbstractRobustConnection = Depends(get_rabbitmq_connection)
):
    try:
        coffee_type_enum = CoffeeType(coffee_type)
        size_enum = CoffeeSize(coffee_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    for ingr in INGREDIENTS_INVENTORY:
        if not await redis.hexists(f"ingredient:{ingr}", "reserved"):
            await redis.hset(f"ingredient:{ingr}", mapping={
                "total": int(INGREDIENTS_INVENTORY[ingr]["total"]),
                "reserved": 0
            })

    order_item = OrderItem(
        coffee_type=coffee_type_enum,
        size=size_enum,
        quantity=quantity
    )

    ingredients_needed = {
        k: int(round(v))  
        for k, v in order_item.get_ingredients().items()
    }

    for ingredient, amount in ingredients_needed.items():
        ingr_name = ingredient.value
        total = int(await redis.hget(f"ingredient:{ingr_name}", "total") or INGREDIENTS_INVENTORY[ingr_name]["total"])
        reserved = int(await redis.hget(f"ingredient:{ingr_name}", "reserved") or 0)
        
        if total - reserved < amount:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно ингредиента {ingr_name}. Доступно: {total - reserved}, требуется: {amount}"
            )

    pipe = redis.pipeline()
    for ingredient, amount in ingredients_needed.items():
        pipe.hincrby(f"ingredient:{ingredient.value}", "reserved", amount)
    await pipe.execute()

    order = OrderResponse(
        customer_name=customer_name,
        items=[order_item],
        ingredients_used=ingredients_needed,
        status=OrderStatus.PENDING
    )

    redis_data = {
        "id": str(order.id),
        "customer_name": order.customer_name,
        "status": order.status.value,
        "items": json.dumps([item.model_dump() for item in order.items]),
        "ingredients_used": json.dumps({k.value: v for k, v in order.ingredients_used.items()}),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat()
    }
    await redis.hset(f"order:{order.id}", mapping=redis_data)
    await redis.expire(f"order:{order.id}", 86400)

    try:
        channel = await rabbit_conn.channel()
        await channel.default_exchange.publish(
            Message(
                body=json.dumps({
                    "id": str(order.id),
                    "status": order.status.value,
                    "ingredients": {k.value: v for k, v in order.ingredients_used.items()}
                }).encode(),
                delivery_mode=2
            ),
            routing_key="coffee_orders"
        )
    except Exception as e:
        async with await redis.pipeline() as pipe:
            for ingredient, amount in order.ingredients_used.items():
                pipe.hincrby(f"ingredient:{ingredient.value}", "reserved", -amount)
            await pipe.execute()
        
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при отправке заказа в очередь: {str(e)}"
        )

    ingredients_info = []
    for ingredient, amount in order.ingredients_used.items():
        ingr_name = ingredient.value
        total = int(await redis.hget(f"ingredient:{ingr_name}", "total") or INGREDIENTS_INVENTORY[ingr_name]["total"])
        reserved = int(await redis.hget(f"ingredient:{ingr_name}", "reserved") or 0)
        
        ingredients_info.append({
            "name": ingr_name,
            "used": amount,
            "reserved": reserved,
            "remaining": total - reserved,
            "unit": "ml" if ingredient in [IngredientType.MILK, IngredientType.WATER] else "g"
        })

    return templates.TemplateResponse(
        "info_page.html",
        {
            "request": request,
            "order_id": str(order.id),
            "customer_name": order.customer_name,
            "coffee_type": coffee_type_enum.value,
            "coffee_size": size_enum.value,
            "quantity": quantity,
            "status": order.status.value,
            "ingredients_info": ingredients_info,
        }
    )

@router.get("/health")
async def health_check(redis: Redis = Depends(get_redis)):
    try:
        if not await redis.ping():
            raise HTTPException(status_code=500, detail="Redis не доступен")
        return {"status": "OK", "redis": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка подключения к Redis: {str(e)}"
        )
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)