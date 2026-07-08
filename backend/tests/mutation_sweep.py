import asyncio, json, re, sys, os
sys.path.insert(0, "/app/backend")
import httpx

BASE = "http://localhost:8001"
LOGIN = {"email": "admin@hotelbox.com", "password": "HotelAdmin2026!"}

async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=15) as c:
        r = await c.post("/api/auth/login", json=LOGIN)
        token = r.json().get("access_token") or r.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        spec = (await c.get("/api/openapi.json")).json()
        failures = []
        sem = asyncio.Semaphore(20)

        async def probe(method, path):
            url = re.sub(r"\{[^}]+\}", "nonexist", path)
            kwargs = {"headers": headers}
            if method in ("post", "put", "patch"):
                kwargs["json"] = {}
            async with sem:
                try:
                    resp = await c.request(method.upper(), url, **kwargs)
                    if resp.status_code >= 500:
                        failures.append((method.upper(), url, resp.status_code, resp.text[:120]))
                except Exception as e:
                    failures.append((method.upper(), url, "EXC", str(e)[:120]))

        tasks = []
        for path, methods in spec["paths"].items():
            for method in methods:
                if method in ("get", "post", "put", "patch", "delete"):
                    tasks.append(probe(method, path))
        print(f"Probing {len(tasks)} endpoints...")
        await asyncio.gather(*tasks)
        print(f"\n=== {len(failures)} FAILURES (5xx) ===")
        for f in sorted(failures):
            print(f)

asyncio.run(main())
