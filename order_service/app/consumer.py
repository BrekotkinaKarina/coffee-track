import asyncio
import json
from datetime import datetime  
from aio_pika import connect_robust, Message
from redis_client import get_redis
from models import OrderStatus

async def update_order_status(redis, order_id: str, new_status: OrderStatus):
    """Обновляет статус заказа в Redis"""
    await redis.hset(
        f"order:{order_id}",
        mapping={
            "status": new_status.value,
            "updated_at": datetime.now().isoformat()  
        }
    )
    print(f"🔄 Обновлен статус заказа {order_id} -> {new_status.value}")

async def process_order(message):
    redis = await get_redis()
    try:
        order_data = json.loads(message.body.decode())
        order_id = order_data["id"]
        
        await update_order_status(redis, order_id, OrderStatus.IN_PROGRESS)
        
        await asyncio.sleep(10)
        
        await update_order_status(redis, order_id, OrderStatus.READY)
        
        await message.ack()
        print(f"✅ Заказ {order_id} готов!")
        
    except Exception as e:
        await update_order_status(redis, order_id, OrderStatus.CANCELLED)
        print(f"❌ Ошибка: {str(e)}")
        await message.nack()

async def consume():
    connection = await connect_robust("amqp://guest:guest@localhost/")
    channel = await connection.channel()
    queue = await channel.declare_queue("coffee_orders", durable=True)
    
    await queue.consume(process_order)
    print("🚀 Consumer запущен. Ожидание заказов...")
    
    try:
        await asyncio.Future() 
    finally:
        await connection.close()

async def process_order(message):
    redis = await get_redis()
    try:
        order_data = json.loads(message.body.decode())
        order_id = order_data["id"]
        
        await update_order_status(redis, order_id, OrderStatus.IN_PROGRESS)
        
        await asyncio.sleep(10)

        order_info = await redis.hgetall(f"order:{order_id}")
        ingredients_used = json.loads(order_info["ingredients_used"])
        
        for ingr, amount in ingredients_used.items():
            await redis.hincrby(f"ingredient:{ingr}", "reserved", -int(amount))

        await update_order_status(redis, order_id, OrderStatus.READY)
        await message.ack()
        
    except Exception as e:
        await update_order_status(redis, order_id, OrderStatus.CANCELLED)
        await message.nack()

if __name__ == "__main__":
    asyncio.run(consume())