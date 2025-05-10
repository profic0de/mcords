from typing import Tuple, Optional
import hashlib
import socket
import struct
import uuid

class Var:
    def recv_all(conn: socket.socket) -> Optional[bytes]:
        """Reads all available bytes until the socket closes or times out"""
        data = b""
        try:
            while True:
                chunk = conn.recv(1)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            # Timeout occurred — return what we have
            pass
        except Exception as e:
            raise Exception(f"Error during recv_all: {e}")
            return None
        return data if data else None

    def recv_exactly(conn: socket.socket, length: int) -> Optional[bytes]:
        """Reads exactly length bytes with timeout handling"""
        data = b""
        while len(data) < length:
            try:
                chunk = conn.recv(length - len(data))
            except socket.timeout:
                return None
            if not chunk:
                return None
            data += chunk
        return data

    def write_string(s: str) -> bytes:
        encoded = s.encode('utf-8')
        return Var.write_varint(len(encoded)) + encoded
    
    def read_string(data: bytes, offset: int = 0) -> tuple[str, int]:
        length, length_size = Var.read_varint_from(data[offset:])
        offset += length_size
        string = data[offset:offset + length].decode('utf-8')
        offset += length
        return string, offset

    def write_varint(value: int) -> bytes:
        """Encodes an integer as a Minecraft VarInt."""
        out = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            if value != 0:
                byte |= 0x80
            out.append(byte)
            if value == 0:
                break
        return bytes(out)

    def read_varint_from_bytes(data: bytes) -> Tuple[int, int]:
        """Reads a VarInt from bytes and returns (value, bytes_consumed)"""
        num = 0
        bytes_read = 0
        for i in range(5):
            if len(data) <= bytes_read:
                raise ValueError("Not enough data for VarInt")
            byte = data[bytes_read]
            bytes_read += 1
            num |= (byte & 0x7F) << (7 * i)
            if not (byte & 0x80):
                break
        return num, bytes_read

    def read_varint_from(data: bytes, offset: int = 0):
        """
        Reads a VarInt from data starting at offset.
        Returns a tuple (value, bytes_consumed).
        """
        num = 0
        for i in range(5):
            byte = data[offset + i]
            num |= (byte & 0x7F) << (7 * i)
            if not (byte & 0x80):
                return num, i + 1
        raise Exception("VarInt too big")

    def read_varint(conn) -> Tuple[Optional[int], bytes]:
        """Reads VarInt from socket with timeout handling"""
        data = b""
        num = 0
        for i in range(5):
            try:
                byte = conn.recv(1)
            except socket.timeout:
                return None, data
            if not byte:
                return None, data
            data += byte
            byte_val = byte[0]
            num |= (byte_val & 0x7F) << (7 * i)
            if not (byte_val & 0x80):
                return num, data
        return None, data  # Malformed VarInt
    
    def read_varint_bytes(data: bytes) -> tuple[bytes, bytes]:
        length, length_size = Var.read_varint_from_bytes(data)
        start = length_size
        end = start + length
        return data[start:end], data[end:]

    def java_hex(digest: bytes) -> str:
        n = int.from_bytes(digest, byteorder='big', signed=True)
        return hex(n)[2:] if n >= 0 else '-' + hex(-n)[2:]

    def write_int(data:int) -> bytes:
        return data.to_bytes(4, byteorder='big', signed=True)
    
    def read_int(data: bytes, offset: int = 0) -> int:
        return int.from_bytes(data[offset:offset+4], byteorder='big', signed=True), 4
    
    def write_bool(data:bool) -> bytes:
        return data.to_bytes()
    
    def read_bool(data: bytes, offset: int = 0) -> bool:
        return bool.from_bytes(data[offset:offset+1]), 1
    
    def write_identifiers(identifiers: list[str]) -> bytes:
        payload = Var.write_varint(len(identifiers))
        for identifier in identifiers:
            payload += Var.write_string(identifier)
        return payload

    def read_identifiers(data: bytes, offset: int = 0) -> tuple[list[str], int]:
        identifiers = []
        total_read = 0

        count, read = Var.read_varint_from_bytes(data[offset:])
        offset += read
        total_read += read

        for _ in range(count):
            str_len, read = Var.read_varint_from_bytes(data[offset:])
            offset += read
            total_read += read

            string = data[offset:offset+str_len].decode("utf-8")
            identifiers.append(string)
            offset += str_len
            total_read += str_len

        return identifiers, total_read

    def write_long(value: int) -> bytes:
        return value.to_bytes(8, byteorder='big', signed=True)

    def read_long(data: bytes, offset: int = 0) -> tuple[int, int]:
        return int.from_bytes(data[offset:offset+8], byteorder='big', signed=True), 8

    def write_hashed_seed(seed: int) -> bytes:
        # Convert seed to bytes (signed 64-bit long)
        seed_bytes = Var.write_long(seed)        
        # SHA-256 hash
        sha256 = hashlib.sha256(seed_bytes).digest()

        # Take the first 8 bytes and convert back to signed long
        hashed = int.from_bytes(sha256[:8], byteorder='big', signed=True)
        return Var.write_long(hashed)

    def write_u8(value: int) -> bytes:
        return value.to_bytes(1, byteorder='big', signed=False)

    def read_u8(data: bytes, offset: int = 0) -> tuple[int, int]:
        return int.from_bytes(data[offset:offset+1], byteorder='big', signed=False), 1

    def write_byte(value: int) -> bytes:
        return value.to_bytes(1, byteorder='big', signed=True)

    def read_byte(data: bytes, offset: int = 0) -> tuple[int, int]:
        return int.from_bytes(data[offset:offset+1], byteorder='big', signed=True), 1

    def get_offline_uuid(username: str) -> str:
        name = f"OfflinePlayer:{username}"
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, name))
    
    def write_nbt(data: dict) -> bytes:
        def encode_long_array(name: str, longs: list[int]) -> bytes:
            result = b'\x0C'  # TAG_Long_Array
            result += Var.write_string(name)  # Use your existing write_string
            result += len(longs).to_bytes(4, 'big')
            for value in longs:
                result += value.to_bytes(8, 'big', signed=True)
            return result

        nbt = b'\x0A' + b'\x00\x00'  # TAG_Compound with empty name
        for key, value in data.items():
            if isinstance(value, list) and all(isinstance(v, int) for v in value):
                nbt += encode_long_array(key, value)
        nbt += b'\x00'  # TAG_End
        return nbt

    def write_float(value: float) -> bytes:
        return struct.pack('>f', value)  # Big-endian float
    
    def read_float(data: bytes) -> tuple[float, bytes]:
        value = struct.unpack('>f', data[:4])[0]
        return value, 4
    
    def write_double(value: float) -> bytes:
        # Writes a double (64-bit floating point) in big-endian order
        return struct.pack('>d', value)

    def read_double(data: bytes) -> tuple[float, bytes]:
        # Reads a double (64-bit floating point) from the beginning of data
        value = struct.unpack('>d', data[:8])[0]
        return value, 8
    
    def write_short(value: int) -> bytes:
        """Encodes a 2-byte signed short integer in big-endian."""
        return struct.pack('>h', value)

    def read_short(data: bytes) -> int:
        """Decodes a 2-byte signed short integer from big-endian bytes."""
        return struct.unpack('>h', data[:2])[0], 2

    def write_position(x: int, y: int, z: int) -> int:
        # Handle negative values using two’s complement
        x &= 0x3FFFFFF
        y &= 0xFFF
        z &= 0x3FFFFFF

        return ((x << 38) | (z << 12) | y)

    def read_position(value: int) -> tuple[int, int, int]:
        x = (value >> 38)
        y = value & 0xFFF
        z = (value >> 12) & 0x3FFFFFF

        # Sign extension
        if x >= 2**25:
            x -= 2**26
        if y >= 2**11:
            y -= 2**12
        if z >= 2**25:
            z -= 2**26

        return x, y, z

    def write_array(arr, write_element_fn = lambda x: x):
        result = Var.write_varint(len(arr))
        for item in arr:
            result += write_element_fn(item)
        return result

    def read_array(data, offset, read_element_fn):
        length, offset = Var.read_varint(data, offset)
        result = []
        for _ in range(length):
            value, offset = read_element_fn(data, offset)
            result.append(value)
        return result, offset
    
    def write_TagString(text:str, actionbar:bool=False):
        r = bytearray()
        r += b'\x08'
        r += Var.write_short(len(text))
        r += text.encode("utf-8")

        r += Var.write_bool(actionbar)
        return r
    
    def write_varint_array(array=[]) -> bytes:
        if len(array) == 0: return Var.write_varint(0)
        output = Var.write_varint(len(array))
        for i in array:
            output += Var.write_varint(i)
        return output
    
    def write_TagCompound(text:str, actionbar:bool=False):
        r = bytearray()
        r += b'\x0a'
        r += Var.write_short(len(text))
        r += text.encode("utf-8")

        r += Var.write_bool(actionbar)
        return r
    
    def write_ushort(value: int) -> bytes:
        """Encodes a 2-byte unsigned short integer in big-endian."""
        return struct.pack('>H', value)

    def read_ushort(data: bytes) -> tuple[int, int]:
        """Decodes a 2-byte unsigned short integer from big-endian bytes."""
        return struct.unpack('>H', data[:2])[0], 2