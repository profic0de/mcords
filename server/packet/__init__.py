from server.vars import Var
import asyncio

class Packet:
    def __init__(self, reader=None, writer=None, ed_key=None, compression=-1):
        from Crypto.Cipher import AES
        self.reader = reader
        self.writer = writer
        self.compression = compression

        if ed_key is not None:
            self.encryption = AES.new(ed_key, AES.MODE_CFB, iv=ed_key, segment_size=8)
            self.decryption = AES.new(ed_key, AES.MODE_CFB, iv=ed_key, segment_size=8)
        else:
            self.encryption = None
            self.decryption = None

    def __check(self, reader_or_writer, is_reader):
        if reader_or_writer is not None:
            if is_reader and isinstance(reader_or_writer, asyncio.StreamReader):
                return reader_or_writer
            elif not is_reader and isinstance(reader_or_writer, asyncio.StreamWriter):
                return reader_or_writer
            else:
                raise TypeError("Provided reader_or_writer does not match expected type.")
        
        # self?
        if is_reader:
            if self.reader is not None and isinstance(self.reader, asyncio.StreamReader):
                return self.reader
        else:
            if self.writer is not None and isinstance(self.writer, asyncio.StreamWriter):
                return self.writer
        
        raise TypeError("No matching reader or writer found.")

    def set_compression(self, compression:int):
        self.compression = compression

    def set_encryption(self, shared_secret:bytes):
        from Crypto.Cipher import AES
        self.encryption = AES.new(shared_secret, AES.MODE_CFB, iv=shared_secret, segment_size=8)
        self.decryption = AES.new(shared_secret, AES.MODE_CFB, iv=shared_secret, segment_size=8)

    async def recv(self, reader: asyncio.StreamReader = None):
        from server.world import logger
        _reader = self.__check(reader, True)
        
        async def read_varint_encrypted() -> int:
            """Reads a VarInt from an encrypted stream."""
            data = b""
            for _ in range(5):  # VarInt can be at most 5 bytes
                byte = await _reader.read(1)
                if not byte:
                    return None, 0, b""
                byte = self.decryption.decrypt(byte)
                data += byte
                if byte[0] & 0x80 == 0:
                    break
            length, _ = Var.read_varint_from_bytes(data)
            return length
        
        if getattr(self, 'encryption', None) != None:
            packet_length = await read_varint_encrypted()
        else:
            packet_length = await Var.read_varint(_reader)

        data = await _reader.read(packet_length)

        if getattr(self, 'encryption', None) != None:
            data = self.decryption.decrypt(data)

        if getattr(self, "compression", -1) > 0:
            from zlib import decompress
            data_length, offset = Var.read_varint_from(data); data = data[offset:]
            if data_length > 0:
                data = decompress(data)

        logger.debug(f'{"🔒 " if self.encryption is not None else ""}Recieved: {data}')
        return data
    
    async def send(self, data: bytes, writer: asyncio.StreamWriter = None):
        from server.world import logger
        from zlib import compress
        _writer = self.__check(writer, False)

        # Apply compression if enabled and data is large enough
        if getattr(self, "compression", -1) > 0:
            threshold = self.compression
            if len(data) >= threshold:
                uncompressed_length = Var.write_varint(len(data))
                data = compress(data)
                data = uncompressed_length + data
            else:
                # No compression, but still need to send a VarInt 0
                data = Var.write_varint(0) + data

        length_prefix = Var.write_varint(len(data))
        data = length_prefix + data

        logger.debug(f'{"🔒 " if self.encryption is not None else ""}Sending: {data}')

        if getattr(self, 'encryption', None) is not None:
            data = self.encryption.encrypt(data)

        _writer.write(data)
        await _writer.drain()
