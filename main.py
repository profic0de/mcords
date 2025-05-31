import asyncio
from traceback import print_exc
from server.cli import Console, colored
from server.config import config
from server.client import handle_client
from server.blocks import *

stop_event = asyncio.Event()
console = Console(stop_event)

async def start_server():
    server = await asyncio.start_server(handle_client, '127.0.0.1', int(config.get("server-port", "25565")))
    addr = server.sockets[0].getsockname()
    console.print(f"✅ Server started on {addr[0]}:{addr[1]}")

    async with server:
        await stop_event.wait()
        console.print("🛑 Server shutting down...")

async def entry():
    tasks = [
        asyncio.create_task(start_server()),
        # asyncio.create_task(world.tick()),
        asyncio.create_task(console.input())
    ]

    try:
        await stop_event.wait()
    except Exception as e:
        console.print(f"🛑 Fatal error: {e}")
        print_exc()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("\nExited cleanly.")

if __name__ == "__main__":
    try:
        asyncio.run(entry())
    except KeyboardInterrupt:
        print("\n🛑 Server shutdown requested via Ctrl+C")
