from server.packet.build import Build
from server.packet.parse import Parse
from server.logger import logger as l
from server.config import config
from server.packet import Packet
from server.player import Player

logger = l.create_sub_logger("world", ["INFO"])

class Engine:
    def __init__(self):
        self.delay = 0.05
        self.messages = []

    def playerId(self):
        # Make sure playerIds exists
        if not hasattr(self, 'playerIds'):
            self.playerIds = set()

        # Find the smallest unused ID starting from 0
        i = 0
        while i in self.playerIds:
            i += 1

        self.playerIds.add(i)
        return i

    async def onJoin(self, player:Player):
        from server.world.states import login, configuration, play
        from server.world import world

        try:
            await login.login(player, True if config.get("online-mode", "false") == "true" else False, int(config.get("network-compression-threshold", "-1")))
            await configuration.config(player)
            await play.play(player)
        except JoinGameError as e:
            logger.info(f"👋 Player {getattr(player, 'username', 'Unknown')} caused error during world join: {e}")
            await world.remove(player)

    async def message(self, player:Player, data:bytes):
        from asyncio import Lock
        from time import time
        with Parse(data) as parse:
            packet_id = parse.varint()
            if packet_id in [0x1d,0x1c]:
                if not hasattr(player, "pos"):
                    class Position:
                        def __init__(self):
                            self.x = 0
                            self.y = 0
                            self.z = 0
                            self.lock = Lock()
                    player.pos = Position()
                async with player.pos.lock:
                    player.pos.x = parse.double()
                    player.pos.y = parse.double()
                    player.pos.z = parse.double()
            elif packet_id == 0x1A:
                player.keepAliveKick = time()
            else:
                self.messages.append((player, data))
    async def tick(self):
        from server.world import world
        from main import palette
        from time import time
        async with world.playersLock:
            players = world.players
        for player in players:
            if (time() - getattr(player, "keepAliveKick", time())) > 5 and player.state == "play":
                logger.info(f"{player.name} Timed out")
                player.disconnect({"text":"Timed out"})
                del player
                continue

            if (time() - getattr(player, "keepAlive", 0)) > 1 and player.state == "play":
                player.keepAlive = time()
                async with Build(0x26, player) as build:
                    build.long(0)

            if hasattr(player, "pos"):
                if not hasattr(player, "data.m"): player.data.m = [0,0]
                n = lambda c: int(c-1) if c < 0 else int(c)
                async with player.pos.lock:
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
        self.messages.clear()

    def playerId(self):
        # Make sure playerIds exists
        if not hasattr(self, 'playerIds'):
            self.playerIds = set()

        # Find the smallest unused ID starting from 0
        i = 0
        while i in self.playerIds:
            i += 1

        self.playerIds.add(i)
        return i

class ClientSideError(Exception):
    def __init__(self, message=""):
        super().__init__(message)

class JoinGameError(Exception):
    def __init__(self, message=""):
        super().__init__(message)

engine = Engine()