from io import BytesIO
from struct import unpack

class Parse:
    def __init__(self, data: bytes):
        self.data = data
        self.stream = None

    def __enter__(self):
        self.stream = BytesIO(self.data)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stream.close()

    def varint(self) -> int:
        num = 0
        shift = 0
        while True:
            byte = self.stream.read(1)
            if not byte:
                raise EOFError("Unexpected end of data while reading varint")
            b = byte[0]
            num |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
            if shift > 35:
                raise ValueError("Varint too big")
        return num

    def string(self) -> str:
        length = self.varint()
        raw = self.stream.read(length)
        if len(raw) < length:
            raise EOFError("Unexpected end of data while reading string")
        return raw.decode("utf-8")

    def short(self) -> int:
        """Decodes a 2-byte signed short integer from big-endian bytes."""
        return unpack('>h', self.stream.read(2))[0]
    
    def long(self) -> int:
        return int.from_bytes(self.stream.read(8), byteorder='big', signed=True)

    def position(self) -> tuple[int, int, int]:
        value = self.long()
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

    def array(self, type) -> list | bytearray:
        items = self.varint()
        if items == 0: return None
        sample = type()

        # If it returned a single byte (or bytes), collect into a bytearray
        if isinstance(sample, (bytes, bytearray)):
            result = bytearray(sample)
            for _ in range(items - 1):
                result.extend(type())
            return result

        # Otherwise collect into a list
        result = [sample]
        for _ in range(items - 1):
            result.append(type())
        return result

    def byte(self) -> bytes:
        return self.stream.read(1)

    def rest(self) -> bytes:
        return self.stream.read()

    def double(self) -> float:
        return unpack('>d', self.stream.read(8))[0]

    def bool(self) -> bool:
        return bool.from_bytes(self.stream.read(1))

    def hashed_slot(self) -> dict:
        if not self.bool(): return {"hasItem":False}
        slot = {"hasItem":True}
        slot["Id"] = self.varint()
        slot["Count"] = self.varint()
        def vi(): return (self.varint(), self.int())
        self.array(vi)
        self.array(self.varint)
        return slot

    def int(self) -> int:
        return int.from_bytes(self.stream.read(4), byteorder='big', signed=True)