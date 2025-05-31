from server.packet.build import Build
from server.packet.parse import Parse
from server.world.engine import JoinGameError
from server.player import Player
from server.config import config as _config
from server.world import logger
from server.vars import Var
from time import time
import asyncio

async def loop(player: Player):
    while True:
        with Parse(await player.packet.recv()) as parse:
            packet_id = parse.varint()
            if packet_id == 0x00:
                player.info = parse.rest()
            elif packet_id == 0x02:
                if parse.string() == "minecraft:brand":
                    player.brand = parse.string()

async def config(player:Player):
    logger.debug(f"⚙️ Step 1: Configuration started")
    # Step 1: Receive Login Start

    try: await asyncio.wait_for(loop(player), timeout=1)
    except asyncio.TimeoutError:
        logger.debug("⚙️ Step 2: Configuration started")
    except ConnectionResetError:
        logger.debug("⚙️ Step 2: Configuration started")

    async with Build(0x01, player) as build:
        build.string("minecraft:brand")
        build.string("mcords")

    async with Build(0x0c, player) as build:
        build.array(["minecraft:vanilla"],build.string)

    async with Build(0x0e, player) as build:
        build.array([{"namespace":"minecraft","id":"core","version":_config.get("version","1.21.5")}],lambda pack: (
        build.string(pack["namespace"]),
        build.string(pack["id"]),
        build.string(pack["version"])
    ))

    with Parse(await player.packet.recv()) as parse:
        packet_id = parse.varint()
        if packet_id != 0x07:
            raise JoinGameError({"text":f"Expected packet 0x07 got: 0x{packet_id:02x}"})
            # await player.disconnect({"text":f"Expected packet 0x07 got: 0x{packet_id:02x}"})

    logger.debug("⚙️ Step 3: Sending regestries")
    from server.world.regestries import main
    await main(player)

    logger.debug("⚙️ Step 4: Sending config succes")
    await player.packet.send(b'\x03') #Config success
    # async with Build(0x03, player) as build:
    #     pass
    with Parse(await player.packet.recv()) as parse:
        packet_id = parse.varint()
        if packet_id != 0x03:
            raise JoinGameError({"text":f"Expected packet 0x03 got: 0x{packet_id:02x}"})
            # await player.disconnect({"text":f"Expected packet 0x03 got: 0x{packet_id:02x}"})
        logger.debug("✅ Config Success")

    player.state = "play"