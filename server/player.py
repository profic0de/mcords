from server.packet import Packet
from server.logger import logger
from json import dumps
import asyncio

logger = logger.create_sub_logger("world", ["ALL"])

class Player:
    def __init__(self, reader:asyncio.StreamReader, writer:asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

        self.info = {}
        self.state = "login"
        self.packet = Packet(reader, writer)

        class Data:
            def __init__(self):
                self.lock = asyncio.Lock()
        self.data = Data()

    async def disconnect(self, message:set):
        if self in self.world.players:
            from server.packet.build import Build
            self.world.players.remove(self)
            async with Build({'l':0x00, 'c':0x02, 'p':0x1C}[self.state[0].lower()], self) as build:
                if self.state[0].lower() == "p":
                    self.world.engine.playerIds.remove(self.Id)
                if self.state[0].lower() in ["c","p"]:
                    build.text(message)
                else:
                    build.string(dumps(message, separators=(",", ":")))
            logger.info(f"Player {getattr(self, "username", "Unknown")} disconnected")
