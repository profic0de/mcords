from server.packet.parse import Parse
from server.packet.build import Build
from server.packet import Packet
from server.client import logger
from properties import MOTD_DATA
from server.vars import Var
# from struct import pack
from json import dumps
import asyncio, traceback

class Handle:
    @staticmethod    
    async def handshake(packet: Packet) -> int:
        """Handles the initial handshake packet."""
        buffer = await packet.recv()
        
        # print(f'{buffer}')
        packet_id, data = buffer[:1], buffer[1:]
        if packet_id != b'\x00':
            logger.warn(f"⚠️ Expected handshake (0x00), got {packet_id}")
            return False
        
        with Parse(data) as parse:
            protocol_version = parse.varint()
            server_addr = parse.string()
            server_port = parse.short()
            next_state = parse.varint()
        
        logger.debug(f"🔍 Handshake: version={protocol_version}, addr={server_addr}:{server_port}, next={next_state}")
        return next_state, protocol_version, f"{server_addr}:{server_port}"

    @staticmethod
    async def status_request(packet: Packet, protocol_version):
        try:
            with Parse(await packet.recv()) as parse:
                packet_id = parse.varint()

            if packet_id is None:
                logger.warn("ℹ️ No status request received (client might have disconnected)")
                return
            if packet_id != 0x00:
                logger.warn(f"⚠️ Expected status request (0x00), got {packet_id}")
                return

            # Send response
            if (MOTD_DATA["version"]["protocol"] == -1):
                response = MOTD_DATA.copy()
                response["version"]["protocol"] = protocol_version
                response = dumps(response)
            else:
                response = dumps(MOTD_DATA)

            async with Build(0x00, packet.writer) as build:
                build.string(response)

            logger.debug("✅ Sent status response")
        except Exception as e:
            logger.error(f"Error durring status request: {e}")

    @staticmethod
    async def ping(packet: Packet):
        try:
            with Parse(await packet.recv()) as parse:
                packet_id = parse.varint()
                timestamp = parse.long()

            if packet_id is None:
                logger.warn("ℹ️ No ping received (normal for some clients)")
                return
            if packet_id != 0x01:
                logger.warn(f"⚠️ Expected ping (0x01), got {packet_id}")
                return
                
            async with Build(0x01, packet.writer) as build:
                build.long(timestamp)

            logger.debug("✅ Responded to ping")
        except Exception as e:
            logger.error(f"Error durring ping: "); traceback.print_exc()
