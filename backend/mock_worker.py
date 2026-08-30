import asyncio, httpx, time, base64

BASE = "http://localhost:8000"
WORKER_TOKEN = "worker_secret_token"
WH = {"X-Worker-Token": WORKER_TOKEN}

async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
        # Register
        r = await c.post("/api/workers/register", json={"name": "mock-ui-worker"}, headers=WH)
        worker_id = r.json()["id"]
        print(f"Registered worker: {worker_id}")

        while True:
            try:
                # Heartbeat
                await c.post(f"/api/workers/{worker_id}/heartbeat", headers=WH)
                
                # Claim
                r = await c.post("/api/jobs/claim", params={"worker_id": worker_id}, headers=WH)
                if r.status_code == 200:
                    job = r.json()
                    if job:
                        print(f"Claimed job: {job['id']}")
                        await asyncio.sleep(2) # Simulate work
                        r2 = await c.post(f"/api/jobs/{job['id']}/complete", json={
                            "render_file_b64": base64.b64encode(b"mock_render").decode(),
                            "glb_file_b64": base64.b64encode(b"mock_glb").decode(),
                        }, headers=WH)
                        print(f"Completed job: {r2.status_code}")
                
            except Exception as e:
                print(f"Worker error: {e}")
            
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
