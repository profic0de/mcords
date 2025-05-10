from server.player import Player
from server.vars import Var
from server.logger import Logger
from server.tools import Tool
import uuid
# from server.proxy import proxy

def process_packet(data_b: bytes, direction: str, player: Player, logger: Logger) -> bytes:
    parse = False
    # logger.debug(f"🔵 [2] [ -> {direction}] - {data_b}")# bytes - {data}")

    packet_id, data = Tool.parse_packet(data_b)
    direction = f"{direction.capitalize()}bound"

    # logger.debug(f"🔵 [1] [ -> {direction.capitalize()}bound] - 0x{packet_id:02x} - {data}")# bytes - {data}")

    if player.proxy["state"] == "login" and direction == "Clientbound" and packet_id == 0x03:
        player.proxy["compression"], offset = Var.read_varint_from(data)
        logger.debug(f"Set compression to: {player.proxy["compression"]}")

        logger.debug(f"🔵 [packet_id, data] - {packet_id, data}")# bytes - {data}")
        packet_id, data = Tool.parse_packet(Tool.decompress_packet(data[offset:]))
        logger.debug(f"🔵 [packet_id, data] - {packet_id, data}")# bytes - {data}")

        parse = True

    if ((player.proxy["state"] == "login" and direction == "Clientbound") or parse) and packet_id == 0x02 :
        # logger.debug(f"[{direction}] - {packet_id:02x} - {len(data)} bytes - {data}")
        player.proxy["state"] = "configuration"
        uuid_str = str(uuid.UUID(bytes=data[:16]))
        player.username, _ = Var.read_string(data, 16)
        logger.debug(f"{player.username} - {uuid_str}")


    # 🔧 Example modification: block chat messages (packet ID 0x03 for clientbound chat in old versions)
    # Only makes sense if you decode the packet — see below
    return data_b  # Return the modified or original packet
