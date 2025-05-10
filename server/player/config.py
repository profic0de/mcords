from server.vars import Var
from server.parse import Parse
import server.registry as re
from server.logger import logger


def config(self):
    logger.debug(f"⚙️  Step 1: started configuration")

    payload = (
        b'\x01' +
        Var.write_string("minecraft") +
        Var.write_string("core") +
        Var.write_string("1.21.5")
    )
    # payload = b'\x01\tminecraft\x04core\x061.21.5'
    self.send_packet(0x0E, payload)

    for payload in re.array:
        self.send_packet(0x07, payload)
    self.send_packet(0x0d, re.tags)
    # del re.array, re.tags

    ids = []
    sent = 0
    while True:
        packet_id, packet_data = self.recv_packet()
        ids.append(packet_id)

        if len(ids) >= 3 and sent == 0:
            sent += 1
            self.send_packet(0x03, b'')        
        
        if packet_id == 0x00:
            data = Parse.packet(0x00, packet_data, "config")
        
        if packet_id == 0x03:
            break

        if self.is_connected() == False:
            raise Exception("Disconnected during configuration")
    del packet_data

    logger.debug("✅ Configuration Success")