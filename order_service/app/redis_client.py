import aio_pika
from aio_pika.abc import AbstractRobustConnection
from redis.asyncio import Redis, ConnectionPool

redis_pool = ConnectionPool.from_url(
    "redis://localhost:6379",
    decode_responses=True,
    max_connections=10
)

async def get_redis() -> Redis:
    return Redis(connection_pool=redis_pool)

RABBITMQ_URL = "amqp://guest:guest@localhost/"

async def get_rabbitmq_connection() -> AbstractRobustConnection:
    return await aio_pika.connect_robust(RABBITMQ_URL)
