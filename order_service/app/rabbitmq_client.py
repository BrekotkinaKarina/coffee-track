from aio_pika.abc import AbstractRobustConnection
from aio_pika import connect_robust

async def get_rabbitmq_connection() -> AbstractRobustConnection:
    return await connect_robust("amqp://guest:guest@localhost/")