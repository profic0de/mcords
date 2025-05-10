from typing import Tuple, Optional
from server.vars import Var

from typing import Tuple, Optional
from server.vars import Var
from server.logger import logger

def recv_packet(self) -> Tuple[Optional[int], bytes]:
    """Receives a full Minecraft packet, handling both encrypted and unencrypted streams."""

    def read_varint_encrypted() -> Tuple[Optional[int], int, bytes]:
        """Reads a VarInt from an encrypted stream."""
        data = b""
        for _ in range(5):  # VarInt can be at most 5 bytes
            byte = self.conn.recv(1)
            if not byte:
                return None, 0, b""
            byte = self.decrypt_cipher.decrypt(byte)
            data += byte
            if byte[0] & 0x80 == 0:
                break
        length, bytes_read = Var.read_varint_from_bytes(data)
        return length, bytes_read, data

    if getattr(self, 'encryption_enabled', False):
        # Read encrypted length prefix byte-by-byte and decrypt
        packet_length, _, length_bytes = read_varint_encrypted()
    else:
        packet_length, length_bytes = Var.read_varint(self.conn)
        length_bytes = b""  # not used if unencrypted

    if packet_length is None or packet_length < 0:
        return None, b""

    # Read rest of the packet
    remaining = Var.recv_exactly(self.conn, packet_length)
    if not remaining:
        return None, b""

    if getattr(self, 'encryption_enabled', False):
        remaining = self.decrypt_cipher.decrypt(remaining)

    raw = remaining

    # Parse the packet ID from decrypted payload
    packet_id, bytes_read = Var.read_varint_from_bytes(raw)

    prefix = "🔒" if getattr(self, 'encryption_enabled', False) else ""
    logger.debug(f"{prefix}📥 Packet ID: {packet_id}, Length: {packet_length}, Data: {raw}")
    return packet_id, raw[bytes_read:]

def send_packet(self, packet_id: int, payload: bytes = b"") -> None:
    """Sends a properly formatted Minecraft packet."""
    packet = Var.write_varint(packet_id) + payload

    if getattr(self, 'encryption_enabled', False):
        # packet = self.encrypt_cipher.encrypt(packet)
        logger.debug(f"🔒📤 Packet ID: {packet_id}, Length: {len(packet)}, Data: {packet}")
    else:
        logger.debug(f"📤 Packet ID: {packet_id}, Length: {len(packet)}, Data: {packet}")

    tosend = Var.write_varint(len(packet)) + packet
    if getattr(self, 'encryption_enabled', False):
        tosend = self.encrypt_cipher.encrypt(tosend)

    self.conn.sendall(tosend)