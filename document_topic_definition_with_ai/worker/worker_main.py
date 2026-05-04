import asyncio
import json
import os
import redis.asyncio as redis
import aio_pika
import httpx
from datetime import datetime

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
SEARCH_API_URL = os.getenv("SEARCH_API_URL", "http://search-api:8000")

async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            body = message.body.decode()
            print(f"Received message: {body[:200]}")
            
            data = json.loads(body)
            task_id = data.get("task_id")
            request = data.get("request")
            
            if not task_id:
                print(f"ERROR: No task_id in message: {data}")
                return
            
            if not request:
                print(f"ERROR: No request in message: {data}")
                return
            
            print(f"Processing task {task_id}: {request.get('query', '')[:50]}...")
            
            redis_client = await redis.from_url(f"redis://{REDIS_HOST}:6379")
            
            try:
                await redis_client.setex(
                    f"task:{task_id}",
                    300,
                    json.dumps({"status": "processing", "started": datetime.now().isoformat()})
                )
                print(f"Task {task_id}: status updated to processing")
                
                async with httpx.AsyncClient(timeout=120.0) as client:
                    print(f"Task {task_id}: calling search-api at {SEARCH_API_URL}/api/v1/search/")
                    response = await client.post(
                        f"{SEARCH_API_URL}/api/v1/search/",
                        json=request
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"Task {task_id}: search-api returned {len(result.get('results', []))} results")
                        
                        await redis_client.setex(
                            f"result:{task_id}",
                            300,
                            json.dumps(result)
                        )
                        
                        await redis_client.setex(
                            f"task:{task_id}",
                            300,
                            json.dumps({"status": "completed", "finished": datetime.now().isoformat()})
                        )
                        print(f"Task {task_id}: completed successfully")
                    else:
                        error_msg = f"Search API returned {response.status_code}: {response.text[:200]}"
                        print(f"Task {task_id}: {error_msg}")
                        raise Exception(error_msg)
                        
            except Exception as e:
                print(f"Task {task_id} failed: {e}")
                await redis_client.setex(
                    f"task:{task_id}",
                    300,
                    json.dumps({"status": "failed", "error": str(e)})
                )
            finally:
                await redis_client.close()
                
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}, body: {message.body[:200]}")
        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()

async def main():
    print(f"Starting worker with config:")
    print(f"  RABBITMQ_HOST: {RABBITMQ_HOST}")
    print(f"  REDIS_HOST: {REDIS_HOST}")
    print(f"  SEARCH_API_URL: {SEARCH_API_URL}")
    
    connection_string = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:5672/"
    print(f"Connecting to RabbitMQ: {connection_string}")
    
    try:
        connection = await aio_pika.connect_robust(connection_string)
        print("Connected to RabbitMQ")
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {e}")
        return
    
    channel = await connection.channel()
    queue = await channel.declare_queue("search_queue", durable=True)
    
    print("Worker started, waiting for messages...")
    print(f"Queue: {queue.name}, messages ready: {queue.declaration.result.message_count if hasattr(queue, 'declaration') else 'unknown'}")
    
    await queue.consume(process_message)
    
    try:
        await asyncio.Future()
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(main())