import asyncio
import httpx
import time

async def submit_job(client: httpx.AsyncClient):
    data = {
        "skin": "Default",
        "bg_dim": "0.95",
        "resolution": "1080p"
    }
    files = {
        "replay": ("test_replay.osr", b"dummy replay data", "application/octet-stream")
    }
    
    start = time.time()
    try:
        response = await client.post("http://localhost:8000/v1/render", data=data, files=files)
        return response.status_code, time.time() - start
    except Exception as e:
        return str(e), time.time() - start

async def main():
    async with httpx.AsyncClient() as client:
        tasks = [submit_job(client) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        successes = 0
        rate_limited = 0
        
        for status, duration in results:
            if status == 202:
                successes += 1
            elif status == 429:
                rate_limited += 1
                
        print(f"Load Test Complete!")
        print(f"Successful submissions: {successes}")
        print(f"Rate limited submissions: {rate_limited}")
        
if __name__ == "__main__":
    asyncio.run(main())
