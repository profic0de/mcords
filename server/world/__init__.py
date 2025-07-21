from server.transfer import resolve_minecraft_srv, ping_minecraft_server
from server.world.engine import JoinGameError, ClientSideError
from server.logger import logger as log
logger = log.create_sub_logger("world")

from server.packet.build import Build
from server.packet.parse import Parse
from server.player import Player
from server.config import config
import time, asyncio

class World:
    def __init__(self, player:Player):
        self.player = player
        self.keepAlive = time.time()

    async def tick(self):
        from server.packet.build import Build
        while True:
            try: data = await asyncio.wait_for(self.player.packet.recv(), timeout=0.05)
            except (asyncio.TimeoutError, ConnectionResetError): pass
            except Exception as e:
                from traceback import format_exc
                if not isinstance(e, ClientSideError):
                    logger.error(f"Exception caught:\n{format_exc()}")
                raise ConnectionResetError
            if data: await self.message(data)
            else: raise ConnectionResetError

            if await tick(self): return self.proxy_value[0]

    async def message(self, data:bytes):
        from time import time
        with Parse(data) as parse:
            packet_id = parse.varint()
            if packet_id in [0x1d,0x1c]:
                if not hasattr(self.player, "pos"):
                    class Position:
                        def __init__(self):
                            self.x = 0
                            self.y = 0
                            self.z = 0
                    self.player.pos = Position()
                self.player.pos.x = parse.double()
                self.player.pos.y = parse.double()
                self.player.pos.z = parse.double()
            elif packet_id == 0x1A:
                self.keepAlive = time()
            elif packet_id == 0x3e:
                parse.varint()
                if parse.position() == (8,1,13):
                    async with Build(0x34, self.player) as build:
                        build.varint(1)
                        build.varint(8)
                        build.text({"text":"Enter server ip:"})
                    async with Build(0x14, self.player) as build:
                        build.varint(1)
                        build.varint(0)
                        build.short(0)
                        build.raw(b'\x01\xc6\x07\x01\x00\x05\x08\x00')
                        build.string("mc.hypixel.net")
            elif packet_id == 0x2e:
                self.player.ip = parse.string()
                async with Build(0x13, self.player) as build:
                        build.varint(1)
                        build.short(0)
                        build.short(0)
            elif packet_id == 0x10:
                parse.varint()
                parse.varint()
                check = parse.short() == 2
                parse.byte()
                parse.varint()
                # def shs(): return (parse.short(), parse.hashed_slot())
                # parse.array(shs)
                if check and getattr(self.player, "ip", "mc.hypixel.net") != "mc.hypixel.net":
                    async with Build(0x72, self.player) as build: build.text({"text":f"Atempting to connect to: {self.player.ip}","color":"green"}); build.bool(0)
                    async with Build(0x22, self.player) as build: build.byte(6, False); build.float(0)

                    if ping_minecraft_server(resolve_minecraft_srv(self.player.ip)).get("players_online",-1) > -1:
                        async with Build(0x72, self.player) as build: build.text({"text":f"Transfering","color":"green"}); build.bool(0)
                        async with Build(0x22, self.player) as build: build.byte(6, False); build.float(0)

                        self.proxy_value = [self.player.ip]
                    else:
                        async with Build(0x72, self.player) as build: build.text({"text":f"Failed to connect to: {self.player.ip}","color":"red"}); build.bool(0)
                        async with Build(0x22, self.player) as build: build.byte(6, False); build.float(0)

                # logger.info(parse.rest())


    async def run(self):
        from server.world.states import login, configuration, play

        try:
            await login.login(self.player, True if config.get("online-mode", "false") == "true" else False, int(config.get("network-compression-threshold", "-1")))
            await configuration.config(self.player)
            await play.play(self.player)
        except Exception as e:
            logger.info(f"👋 Player {getattr(self.player, 'username', 'Unknown')} caused error during world join: {e}")
            raise JoinGameError
                
        from main import palette
        async with Build(0x08, self.player) as build:
            build.position(8, 1, 13)
            build.varint(palette['minecraft:anvil']+2)

        return await self.tick()
    
async def tick(self):
    from server.packet.build import Build
    from server.world import logger
    from main import palette
    from time import time
    player = self.player
    if (time() - getattr(player, "keepAliveKick", time())) > 5 and player.state == "play":
        logger.info(f"{player.name} Timed out")
        player.disconnect({"text":"Timed out"})
        del player

    if (time() - getattr(player, "keepAlive", 0)) > 1 and player.state == "play":
        player.keepAlive = time()
        async with Build(0x26, player) as build:
            build.long(0)            

    if hasattr(player, "pos"):
        if not hasattr(player, "data.m"): player.data.m = [0,0]
        n = lambda c: int(c-1) if c < 0 else int(c)
        x = player.pos.x
        z = player.pos.z
        if (0 < x < 1) and (0 < z < 1): x,z = 0,0
        m = [n(x),n(z)]
        # async with Build(0x50, player) as build: build.text({"text":f"M: {[x,z]}; {m}{f", P: {player.data.p}" if hasattr(player.data, "p") else ""}"})
        if player.data.m != m or (m == [0,0] and getattr(player.data, "bonce", 0) == 0):
            if m == [0,0]: player.data.bonce = 1
            else: player.data.bonce = 0
            player.data.m = m
            if not hasattr(player.data, "p"): player.data.p = [0,0]
            # async with Build(0x50, player) as build: build.text({"text":f"M: {m}, P: {player.data.p}"})

            block = lambda pos: "minecraft:gray_concrete" if ((pos[0] // 2) % 2) == ((pos[1] // 2) % 2) else "minecraft:light_gray_concrete"
            async with Build(0x08, player) as build:
                build.position(player.data.p[0],0,player.data.p[1])
                build.varint(palette[block(player.data.p)])
            async with Build(0x08, player) as build:
                build.position(m[0],0,m[1])
                build.varint(palette["minecraft:white_concrete"])
                # player.executed = 0
            player.data.p = m

    if getattr(self, "proxy_value", ""):
        return True