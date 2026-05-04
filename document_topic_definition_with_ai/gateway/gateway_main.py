from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
import json
import redis.asyncio as redis
import aio_pika
from datetime import datetime
import os

app = FastAPI(title="Search Gateway with Queue")


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "http://search-api:8000")


redis_client = None
rabbit_channel = None

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    engine: str = "hybrid"
    hubs: Optional[List[str]] = None
    tags: Optional[List[str]] = None

@app.on_event("startup")
async def startup():
    global redis_client, rabbit_channel
    redis_client = await redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}")
    
    connection = await aio_pika.connect_robust(
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}/"
    )
    rabbit_channel = await connection.channel()
    await rabbit_channel.declare_queue("search_queue", durable=True)

@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()

@app.get("/health")
@app.get("/api/v1/search/health")
async def health_check():
    return {"status": "healthy", "service": "search-gateway"}

@app.post("/api/v1/search")
async def create_task(request: SearchRequest):
    task_id = str(uuid.uuid4())
    
    await redis_client.setex(
        f"task:{task_id}",
        300,
        json.dumps({
            "status": "queued",
            "created": datetime.now().isoformat(),
            "request": request.dict()
        })
    )
    
    await rabbit_channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps({
                "task_id": task_id,
                "request": request.dict()
            }).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key="search_queue",
    )
    
    return {"task_id": task_id, "status": "queued"}

@app.get("/api/v1/search/result/{task_id}")
async def get_result(task_id: str):
    result_key = f"result:{task_id}"
    result_data = await redis_client.get(result_key)
    
    if result_data:
        return json.loads(result_data)
    
    task_key = f"task:{task_id}"
    task_data = await redis_client.get(task_key)
    
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = json.loads(task_data)
    return {"task_id": task_id, "status": task.get("status", "processing")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)