from server.world.engine import engine, logger
from threading import Thread, Lock
from server.player import Player
import time, asyncio

class World:
    def __init__(self):
        self.players = []

        self.keepAlive = time.time()
        self.engine = engine
        self.playersLock = asyncio.Lock()

    async def join(self, player:Player):
        async with self.playersLock:
            self.players.append(player)
        player.world = self
        await engine.onJoin(player)

    async def tick(self):
        from server.packet.build import Build
        while True:
            if not self.players or not any(p.state == "play" for p in self.players):
                await asyncio.sleep(engine.delay)
                continue

            # Read from all players in parallel
            tasks = [self.poll_player(p) for p in self.players]
            await asyncio.gather(*tasks)
            await engine.tick()
            # await asyncio.sleep(0.05)

    async def remove(self, player:Player):
        # from inspect import currentframe
        # logger.debug(f"Disconnect function was called from: {currentframe().f_back.f_code.co_name}")

        if player in self.players:
            # self.players.remove(player)
            await player.disconnect({"text":"Disconnected","color":"red"})

    async def poll_player(self, player:Player):
        from traceback import format_exc
        from server.world.engine import ClientSideError
        try:
            data = await asyncio.wait_for(player.packet.recv(), timeout=0.05)
            if data:
                await engine.message(player, data)
                # logger.debug(f"Got: {data}")
            else:
                await self.remove(player)
        except asyncio.TimeoutError:
            pass
        except ConnectionResetError:
            # logger.debug(f"ConnectionResetError")
            # await world.remove(player)
            pass
        except ClientSideError:
            logger.error(f"Clientside error")
            await self.remove(player)
        except Exception as e:
            logger.error(f"Exception caught:\n{format_exc()}")
            await self.remove(player)