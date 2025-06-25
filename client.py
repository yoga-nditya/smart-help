import asyncio
import websockets

async def listen():
    client_id = "1bfaswK8zZ"
    client_secret = "JO7Ztf0Fp1VUQRgwWAi1Cr0SJQL3mUu1"
    uri = f"ws://localhost:8000/ws/available-rooms?client_id={client_id}&client_secret={client_secret}"

    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello from Python client")  # kirim pesan awal

        while True:
            msg = await websocket.recv()
            print("Pesan dari server:", msg)

asyncio.run(listen())
