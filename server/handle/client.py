from server.packet import Packet  # ✅ Absolute import
from server.player import Player
from server.world import world
from server.proxy import proxy
from server.logger import logger
from server.vars import Var
from json import dumps

packet = Packet()

def client(conn):
        error = 0
        try:
            logger.debug(f"🔗 New connection from {conn.getpeername()}")
            
            # Handle handshake
            next_state, protocol, addr = packet.handle_handshake(conn)

            if next_state == None:
                return
            if next_state == 1:
                # Handle status request and ping
                packet.handle_status_request(conn, protocol)
                packet.handle_ping(conn)
            if next_state == 2:
                player = Player(conn, protocol)
                player.login(online_mode=False)
                player.config()
                player.addr = addr

                packet.handle_ingame_login(player)
                world.join(player)
                # logger.debug(f"✅ Player {player.username} handed over to the world")
            if next_state == 3:
                # packet.send_packet(conn, 0x00, Var.write_string(dumps({"text":"We're sorry but the transfers are not currently supported :("}, separators=(",", ":"))));return
                player = Player(conn, protocol)
                player.addr = addr

                proxy.join(player)
                # logger.info(f"✅ Player {player.username} handed over to the proxy")
            if next_state-1 not in range(3):
                logger.warn(f"⚠️  Unknown state received: {next_state}")

        except Exception as e:
            conn.close()
            error = 1
            logger.error(f"❌ Error handling client: {str(e)}")
        finally:
            if error == 1:
                logger.debug("🔌 Connection closed")
