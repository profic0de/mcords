from server.world.engine import ClientSideError
from server.packet.parse import Parse
from server.packet.build import Build
from server.transfer import Transfer
from server.logger import logger
from server.player import Player
from server.handle import Handle
from server.packet import Packet
from server.world import World
from server.vars import Var
import traceback, asyncio

logger = logger.create_sub_logger("client", ["ALL"])

async def handle_client(reader, writer):
    packet = Packet(reader, writer)
    error = 0
    logger.debug(f"🔗 New connection from {writer.get_extra_info('peername')}")

    try:
        next_state, protocol, addr = await Handle.handshake(packet)

        # async with Build(0x00, writer) as build:
        #     build.string(json.dumps([
        #         {"text": "❌ Failed to connect to the target server: ", "color": "red"},
        #         {"text": "Work in progress", "color": "white"}
        #     ], separators=(",", ":")))

        if next_state is None:
            return

        if next_state == 1:
            await Handle.status_request(packet, protocol)
            await Handle.ping(packet)

        if next_state == 2:
            player = Player(reader, writer)
            world = World(player)
            ip = await world.run()
            logger.info(f'📡 Transfering {player.username} to {ip}')
            await Transfer.to(player, ip)
            await asyncio.sleep(1)

        if next_state == 3:
            player = Player(reader, writer)
            world = World(player)
            ip = await world.run()
            logger.info(f'📡 Transfering {player.username} to {ip}')
            await Transfer.to(player, ip)
            await asyncio.sleep(1)

        if next_state - 1 not in range(3):
            logger.warn(f"⚠️  Unknown state received: {next_state}")

    except ConnectionResetError:
        if next_state == 2: logger.info(f"👋 {getattr(player, "username", None)} left the world.")
        else: logger.warn(f"⚠️ Client forcibly closed the connection")
    except ClientSideError:
        logger.error(f"❌ An error ocured on the clientside")
    except Exception as e:
        error = 1
        logger.error(f"❌ Error handling client:\n{traceback.format_exc()}")
    finally:
        if error:
            logger.debug("🔌 Connection closed")
