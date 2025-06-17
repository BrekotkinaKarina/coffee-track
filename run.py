import subprocess
import sys
from multiprocessing import Process

def run_fastapi():
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "order_service.app.api:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])

def run_consumer():
    subprocess.run([
        sys.executable, "-m",
        "order_service.app.consumer"
    ])

if __name__ == "__main__":
    fastapi_process = Process(target=run_fastapi)
    consumer_process = Process(target=run_consumer)
    
    fastapi_process.start()
    consumer_process.start()
    
    fastapi_process.join()
    consumer_process.join()