import asyncio
import zlib
import io
import struct
from typing import Optional, Union, TypeVar, Generic, AsyncIterator

# Cryptography dependencies
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

# Assume these are defined elsewhere in the original crate
# Placeholder values based on typical Minecraft limits
MAX_PACKET_SIZE = 2097152  # 2MB
MAX_PACKET_DATA_SIZE = 2097152 # 2MB (uncompressed)
CompressionThreshold = int # Type alias for clarity

# Define RawPacket
class RawPacket:
    def __init__(self, id: int, payload: bytes):
        self.id = id
        self.payload = payload

    def __repr__(self):
        # Rust debug print equivalent, showing first few bytes of payload
        payload_repr = self.payload[:20]
        if len(self.payload) > 20:
            payload_repr += b"..."
        return f"RawPacket(id={self.id}, payload={payload_repr!r})"

# Define custom errors
class ReadingError(Exception):
    """General error during reading."""
    def __init__(self, message: str, clean_eof: bool = False):
        super().__init__(message)
        self.clean_eof = clean_eof

    @staticmethod
    def CleanEOF(message: str):
        return ReadingError(message, clean_eof=True)

class PacketDecodeError(Exception):
    """Errors specific to packet decoding."""
    def __init__(self, message: str):
        super().__init__(message)

class DecodeIDError(PacketDecodeError):
    """failed to decode packet ID"""
    def __init__(self):
        super().__init__("failed to decode packet ID")

class TooLongError(PacketDecodeError):
    """packet exceeds maximum length (decompressed size too large)"""
    def __init__(self):
        super().__init__("packet exceeds maximum length")

class OutOfBoundsError(PacketDecodeError):
    """packet length is out of bounds (total packet size too large)"""
    def __init__(self):
        super().__init__("packet length is out of bounds")

class MalformedLengthError(PacketDecodeError):
    """malformed packet length VarInt"""
    def __init__(self, details: str):
        super().__init__(f"malformed packet length VarInt: {details}")

class FailedDecompressionError(PacketDecodeError):
    """failed to decompress packet"""
    def __init__(self, details: str):
        super().__init__(f"failed to decompress packet: {details}")

class NotCompressedError(PacketDecodeError):
    """packet is uncompressed but greater than the threshold"""
    def __init__(self):
        super().__init__("packet is uncompressed but greater than the threshold")

class ConnectionClosedError(PacketDecodeError):
    """the connection has closed"""
    def __init__(self):
        super().__init__("the connection has closed")

# Implement the From<ReadingError> for PacketDecodeError logic
# This is handled by catching ReadingError and raising the appropriate PacketDecodeError
# in the get_raw_packet method.

# Implement VarInt
class VarInt:
    def __init__(self, value: int = 0):
        self.value = value

    async def decode_async(self, reader: asyncio.StreamReader) -> 'VarInt':
        """Reads a VarInt from an async reader."""
        value = 0
        num_read = 0
        while True:
            try:
                read_byte_data = await reader.readexactly(1)
            except asyncio.IncompleteReadError:
                 # Treat incomplete read as connection closed if no bytes were read yet for this VarInt
                 if num_read == 0:
                     raise ReadingError.CleanEOF("Connection closed while reading VarInt")
                 else:
                     # Malformed VarInt if it ends unexpectedly mid-value
                     raise ReadingError(f"Incomplete VarInt read after {num_read} bytes")
            except Exception as e:
                 raise ReadingError(f"Error reading byte for VarInt: {e}")

            read_byte = read_byte_data[0]
            value |= (read_byte & 0x7F) << (7 * num_read)

            num_read += 1
            if num_read > 5: # VarInts are typically at most 5 bytes for 32-bit values
                 raise ReadingError("VarInt is too long")

            if not (read_byte & 0x80):
                break

        # Minecraft VarInts are signed 32-bit. The decoding above produces an unsigned value.
        # For positive values, this is fine. For negative values, the 5th byte will have
        # the sign bit set (0x80) and the value will be large.
        # The standard decoding handles this correctly up to 5 bytes for signed values.
        # The check `num_read > 5` is sufficient for standard VarInts.
        # We store the decoded integer value directly.

        return VarInt(value)

    def encode(self, writer: io.BytesIO):
        """Writes a VarInt to a synchronous writer."""
        value = self.value
        # Handle 0 explicitly
        if value == 0:
            writer.write(b'\x00')
            return

        # Handle negative numbers (Minecraft VarInts are signed)
        # Python's bitwise ops handle signed ints correctly for this encoding logic
        # as long as we don't exceed the standard VarInt range.
        # The loop condition `value != 0` needs adjustment for negative numbers.
        # A common way is to treat it as unsigned during encoding loop.
        # Let's use a mask for the sign bit check.
        unsigned_value = value & 0xFFFFFFFF # Treat as unsigned 32-bit

        while True:
            byte = unsigned_value & 0x7F
            unsigned_value >>= 7
            if unsigned_value != 0:
                byte |= 0x80
            writer.write(bytes([byte]))
            if unsigned_value == 0:
                break


    def written_size(self) -> int:
        """Calculates the number of bytes the VarInt will take when encoded."""
        value = self.value
        if value == 0:
            return 1
        # Calculate size for signed value
        unsigned_value = value & 0xFFFFFFFF
        size = 0
        while True:
            size += 1
            if (unsigned_value & 0xFFFFFF80) == 0: # Check if the remaining value fits in 7 bits
                 break
            unsigned_value >>= 7
        return size

# Helper for creating StreamReader from bytes for tests
def create_stream_reader(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader

# Implement Async Reader Wrappers

# Bounded Reader
class BoundedAsyncReader(asyncio.StreamReader):
    """An async reader that reads at most `limit` bytes from an inner reader."""
    def __init__(self, inner: asyncio.StreamReader, limit: int):
        super().__init__() # StreamReader needs loop, but we won't use its internal buffer/loop directly
        self._inner = inner
        self._limit = limit
        self._read_count = 0
        self._eof = False # Track if we've hit the limit or inner EOF

    async def read(self, n: int = -1) -> bytes:
        if self._eof:
            return b""

        # Determine how many bytes to attempt to read
        remaining_in_limit = self._limit - self._read_count
        if remaining_in_limit <= 0:
            self._eof = True
            return b""

        if n == -1: # Read all remaining up to limit
            bytes_to_attempt = remaining_in_limit
        else: # Read up to n bytes, but not exceeding limit
            bytes_to_attempt = min(n, remaining_in_limit)

        if bytes_to_attempt <= 0:
             return b"" # Should be caught by remaining_in_limit check, but double check

        # Read from the inner reader
        data = await self._inner.read(bytes_to_attempt)

        if not data:
            # Inner reader hit EOF before we hit the limit
            self._eof = True
            return b""

        self._read_count += len(data)

        if self._read_count >= self._limit:
            self._eof = True # Reached the limit

        return data

    async def readexactly(self, n: int) -> bytes:
        if self._eof:
             raise asyncio.IncompleteReadError(b"", n) # Cannot read if already at EOF

        remaining_in_limit = self._limit - self._read_count
        if n > remaining_in_limit:
            # Cannot read exactly n bytes if it exceeds the limit.
            # Read all available up to the limit and then raise IncompleteReadError.
            data = await self.read(remaining_in_limit)
            raise asyncio.IncompleteReadError(data, n)

        # Otherwise, we can read exactly n bytes from the inner reader
        # The inner reader's readexactly will handle reading until n bytes are available or it hits EOF.
        # If the inner reader hits EOF before providing n bytes, it raises IncompleteReadError,
        # which is the correct behavior for our bounded reader as well.
        data = await self._inner.readexactly(n)

        self._read_count += len(data)
        # If readexactly succeeded, len(data) == n.
        # Check if this read reached or exceeded the limit (should only reach exactly if n == remaining_in_limit)
        if self._read_count >= self._limit:
             self._eof = True

        return data

# Stream Decryptor
class StreamDecryptor(asyncio.StreamReader):
    """An async reader that decrypts data from an inner reader using AES-128 CFB-8."""
    def __init__(self, cipher: Cipher, inner: asyncio.StreamReader):
        super().__init__()
        self._inner = inner
        self._decryptor = cipher.decryptor()
        # The cryptography library's CFB8 mode handles the state automatically.

    async def read(self, n: int = -1) -> bytes:
        # Read data from the inner stream.
        # The decryptor can process any length.
        # Reading up to n bytes from inner and decrypting is the direct approach.
        data = await self._inner.read(n)
        if not data:
            return b""
        # Decrypt the data. update() returns decrypted data corresponding to the input.
        decrypted_data = self._decryptor.update(data)
        return decrypted_data

    async def readexactly(self, n: int) -> bytes:
        # Read exactly n bytes from the inner stream.
        # The inner reader's readexactly handles reading until n bytes are available or EOF.
        data = await self._inner.readexactly(n)
        # Decrypt the data.
        decrypted_data = self._decryptor.update(data)
        return decrypted_data

# Zlib Decoder (Async Wrapper)
class AsyncZlibDecoder(asyncio.StreamReader):
    """An async reader that decompresses Zlib data from an inner reader."""
    def __init__(self, inner: asyncio.StreamReader):
        super().__init__()
        self._inner = inner
        self._decompressor = zlib.decompressobj()
        self._buffer = b"" # Buffer for decompressed data
        self._inner_eof = False # Track if the inner reader has reached EOF

    async def _fill_buffer(self):
        """Reads from inner, decompresses, and fills the buffer."""
        if self._inner_eof:
            return # Cannot read more if inner is at EOF

        # Read a chunk of compressed data from the inner reader.
        # Use a reasonable chunk size, similar to BufReader.
        chunk_size = 4096

        try:
            compressed_data = await self._inner.read(chunk_size)
        except asyncio.IncompleteReadError as e:
             # If inner reader hits EOF unexpectedly, process partial data and mark inner EOF
             compressed_data = e.partial
             self._inner_eof = True
             # Process the partial data
             try:
                 decompressed_chunk = self._decompressor.decompress(compressed_data)
                 self._buffer += decompressed_chunk
             except zlib.error as ze:
                 raise FailedDecompressionError(f"Zlib decompression error processing partial data: {ze}")
             except Exception as ex:
                 raise FailedDecompressionError(f"Unexpected error processing partial Zlib data: {ex}")

        if not compressed_data:
            # Inner reader hit EOF normally. Mark inner EOF.
            self._inner_eof = True
            # Attempt to flush the decompressor to get any remaining data.
            try:
                remaining_flush = self._decompressor.flush()
                if remaining_flush:
                    self._buffer += remaining_flush
                # Check for unused data after flush, which indicates a malformed stream.
                if self._decompressor.unused_data:
                     raise FailedDecompressionError("Zlib stream ended unexpectedly with unused data")
            except zlib.error as ze:
                raise FailedDecompressionError(f"Zlib decompression error during flush: {ze}")
            except Exception as ex:
                raise FailedDecompressionError(f"Unexpected error during Zlib flush: {ex}")
            return # No more compressed data to read

        # Decompress the chunk
        try:
            decompressed_chunk = self._decompressor.decompress(compressed_data)
            self._buffer += decompressed_chunk
        except zlib.error as ze:
            raise FailedDecompressionError(f"Zlib decompression error: {ze}")
        except Exception as ex:
            raise FailedDecompressionError(f"Unexpected error during Zlib decompress: {ex}")


    async def read(self, n: int = -1) -> bytes:
        # If n is -1, read all remaining data.
        if n == -1:
            all_data = b""
            while True:
                # Keep filling buffer and reading until no more data is produced
                await self._fill_buffer()
                if not self._buffer and self._inner_eof:
                    break # No more data and inner stream is done
                if not self._buffer:
                    # Should not happen if inner_eof is False, _fill_buffer should add to buffer
                    # unless the compressed stream is malformed or empty.
                    # If _fill_buffer read from inner but got no decompressed output, loop again.
                    # If _fill_buffer got EOF from inner and flushed, and buffer is still empty, break.
                    if not self._inner_eof:
                         # If inner is not EOF but buffer is empty after fill, something is wrong or need more input
                         # Let's assume _fill_buffer will eventually add to buffer unless inner is truly exhausted.
                         # If inner is exhausted, _inner_eof will be True.
                         pass # Continue loop
                    else:
                         break # Inner EOF and buffer is empty

                # Take all data from buffer
                data = self._buffer
                self._buffer = b""
                all_data += data

            return all_data

        # If n is specified, read up to n bytes.
        while len(self._buffer) < n and not self._inner_eof:
            await self._fill_buffer()
            # If buffer is still empty after filling and inner is EOF, break
            if not self._buffer and self._inner_eof:
                 break

        # Serve from the buffer
        if not self._buffer:
            return b"" # Buffer is empty (either EOF or waiting for more compressed data)

        if n >= len(self._buffer):
            data = self._buffer
            self._buffer = b""
            return data
        else:
            data = self._buffer[:n]
            self._buffer = self._buffer[n:]
            return data

    async def readexactly(self, n: int) -> bytes:
        # Read exactly n bytes. This might require multiple reads from the inner stream
        # and multiple decompress calls until n bytes are buffered.
        while len(self._buffer) < n and not self._inner_eof:
            await self._fill_buffer()
            # If buffer is still empty after filling and inner is EOF, we cannot satisfy readexactly
            if not self._buffer and self._inner_eof:
                 raise asyncio.IncompleteReadError(self._buffer, n)

        # If we exited the loop because inner_eof is True but buffer < n, the exception was raised.
        # If we exited because len(self._buffer) >= n, we have enough data.
        if len(self._buffer) < n:
             # This case should be caught by the check inside the loop, but double-check.
             # It means we are at inner_eof but don't have enough data.
             raise asyncio.IncompleteReadError(self._buffer, n)

        # We have at least n bytes in the buffer
        data = self._buffer[:n]
        self._buffer = self._buffer[n:]
        return data

# Aes128Cfb8Dec equivalent using cryptography
class Aes128Cfb8Dec:
    def __init__(self, key: bytes, iv: bytes):
        # Key and IV must be 16 bytes for AES-128
        if len(key) != 16 or len(iv) != 16:
            raise ValueError("Key and IV must be 16 bytes for AES-128 CFB-8")
        self._cipher = Cipher(algorithms.AES(key), modes.CFB8(iv), backend=default_backend())

    def decryptor(self):
        # Return a new decryptor instance for a stream
        return self._cipher.decryptor()

    @staticmethod
    def new_from_slices(key: bytes, iv: bytes) -> 'Aes128Cfb8Dec':
        # Rust's new_from_slices returns Result, handle potential errors
        # In Python, we raise ValueError in __init__
        return Aes128Cfb8Dec(key, iv)


# Network Decoder
class NetworkDecoder:
    def __init__(self, reader: asyncio.StreamReader):
        # The reader can be the raw stream, or a StreamDecryptor wrapping it.
        # We'll manage this state internally.
        self._reader: asyncio.StreamReader = reader # Initially the raw reader
        self._compression: Optional[CompressionThreshold] = None
        self._is_encrypted: bool = False # Track if encryption is enabled

    def set_compression(self, threshold: CompressionThreshold):
        self._compression = threshold

    # NOTE: Encryption can only be set; a minecraft stream cannot go back to being unencrypted
    def set_encryption(self, key: bytes):
        if self._is_encrypted:
            # panic!("Cannot upgrade a stream that already has a cipher!")
            raise RuntimeError("Cannot upgrade a stream that already has a cipher!")

        # Rust uses key as IV for AES-128 CFB-8
        try:
            cipher = Aes128Cfb8Dec.new_from_slices(key, key)
        except ValueError as e:
            # expect("invalid key")
            raise ValueError(f"Invalid key for AES-128 CFB-8: {e}")

        # Replace the current reader with a StreamDecryptor wrapping it
        self._reader = StreamDecryptor(cipher, self._reader)
        self._is_encrypted = True

    async def get_raw_packet(self) -> RawPacket:
        # Read packet length (VarInt)
        try:
            packet_len_varint = await VarInt().decode_async(self._reader)
            packet_len = packet_len_varint.value
        except ReadingError as err:
            # map_err(|err| match err { ... })
            if err.clean_eof:
                raise ConnectionClosedError()
            else:
                raise MalformedLengthError(str(err))
        except Exception as e:
             # Catch any other unexpected errors during VarInt decode
             raise MalformedLengthError(f"Unexpected error decoding length: {e}")

        # packet_len = packet_len.0 as u64; # Rust converts VarInt(i32) to u64
        # Python VarInt value is just an int. Max Minecraft packet length fits in i32.
        # Let's keep it as int.

        # if !(0..=MAX_PACKET_SIZE).contains(&packet_len) { ... }
        if not (0 <= packet_len <= MAX_PACKET_SIZE):
            raise OutOfBoundsError()

        # let mut bounded_reader = (&mut self.reader).take(packet_len);
        # Create a bounded reader that reads at most packet_len bytes from the current reader
        bounded_reader = BoundedAsyncReader(self._reader, packet_len)

        # let mut reader = if let Some(threshold) = self.compression { ... } else { ... }
        reader_for_payload: asyncio.StreamReader # This will be the reader we read packet ID and payload from

        if self._compression is not None:
            # Compression is enabled
            threshold = self._compression

            # Read decompressed length (VarInt) from the bounded reader
            try:
                decompressed_length_varint = await VarInt().decode_async(bounded_reader)
                decompressed_length = decompressed_length_varint.value
            except ReadingError as err:
                 # This VarInt is read from the bounded reader, which wraps the main reader.
                 # If the bounded reader hits its limit or the underlying reader hits EOF
                 # before the VarInt is fully read, it's a malformed packet.
                 # The Rust code maps ReadingError to PacketDecodeError::FailedDecompression
                 # for this specific VarInt read. Let's follow that.
                 raise FailedDecompressionError(f"Malformed decompressed length VarInt: {err}")
            except Exception as e:
                 raise FailedDecompressionError(f"Unexpected error decoding decompressed length: {e}")


            # let raw_packet_length = packet_len as usize - decompressed_length.written_size();
            # The length of the compressed data + packet ID VarInt
            # The total packet length (packet_len) includes the length VarInt itself.
            # The bounded_reader starts *after* the initial packet_len VarInt.
            # So, bounded_reader contains: VarInt(decompressed_length) + compressed_data
            # The size of the compressed data is packet_len - size_of_VarInt(decompressed_length)
            compressed_data_length = packet_len - decompressed_length_varint.written_size()

            # let decompressed_length = decompressed_length.0 as usize; # Already an int

            # if !(0..=MAX_PACKET_DATA_SIZE).contains(&decompressed_length) { ... }
            if not (0 <= decompressed_length <= MAX_PACKET_DATA_SIZE):
                raise TooLongError() # This error name means decompressed size is too large

            # if decompressed_length > 0 { ... } else { ... }
            if decompressed_length > 0:
                # Data is compressed
                # DecompressionReader::Decompress(ZlibDecoder::new(BufReader::new(bounded_reader)))
                # The bounded_reader now contains only the compressed data (after the decompressed_length VarInt)
                # We need a reader that reads *only* the compressed data part from the bounded reader.
                # The bounded_reader itself is already limited to the total packet data (decompressed_length VarInt + compressed_data).
                # We just read the decompressed_length VarInt from it. The remaining bytes in bounded_reader
                # are the compressed data.
                # So, the ZlibDecoder should wrap the *remaining* part of the bounded_reader.
                # The BoundedAsyncReader needs to support reading the remaining bytes after some have been read.
                # Its `read` method already handles this by tracking `_read_count`.
                # So, we can just pass the same `bounded_reader` to the `AsyncZlibDecoder`.
                reader_for_payload = AsyncZlibDecoder(bounded_reader)
            else:
                # Data is not compressed (decompressed_length is 0)
                # Validate that we are not less than the compression threshold
                # if raw_packet_length > threshold { ... }
                # raw_packet_length in Rust seems to be the size of the data *after* the decompressed_length VarInt
                # when decompressed_length is 0. This is the size of the uncompressed packet ID + payload.
                # In the uncompressed case (decompressed_length == 0), the packet structure is:
                # packet_len VarInt | decompressed_length VarInt (0) | packet_id VarInt | payload
                # The bounded_reader contains: decompressed_length VarInt (0) | packet_id VarInt | payload
                # After reading the decompressed_length VarInt (which is 0), the remaining bytes in bounded_reader
                # are the uncompressed packet ID VarInt + payload.
                # The size of these remaining bytes is `compressed_data_length` calculated above.
                # This `compressed_data_length` is the size of the uncompressed packet (ID + payload).
                # This is the value that should be compared against the threshold.
                uncompressed_packet_size = compressed_data_length # This is the size of packet_id VarInt + payload

                if uncompressed_packet_size > threshold:
                    raise NotCompressedError()

                # DecompressionReader::None(bounded_reader)
                # The reader for payload is the bounded reader itself, as it contains the uncompressed data.
                reader_for_payload = bounded_reader
        else:
            # Compression is not enabled
            # DecompressionReader::None(bounded_reader)
            # The bounded_reader contains: packet_id VarInt | payload
            reader_for_payload = bounded_reader

        # TODO: Serde is sync so we need to write to a buffer here :(
        # Is there a way to deserialize in an asynchronous manner?
        # Python's standard libraries (like zlib) are sync. We handled this in AsyncZlibDecoder
        # by buffering. Reading the packet ID and payload will use the async reader methods.

        # let packet_id = VarInt::decode_async(&mut reader) ...
        try:
            packet_id_varint = await VarInt().decode_async(reader_for_payload)
            packet_id = packet_id_varint.value
        except ReadingError as err:
             # This VarInt is read from the reader_for_payload (either BoundedAsyncReader or AsyncZlibDecoder)
             # If it fails, it's a decode ID error.
             raise DecodeIDError() # Rust maps any error here to DecodeID
        except Exception as e:
             # Catch any other unexpected errors during VarInt decode
             raise DecodeIDError() # Rust maps any error here to DecodeID


        # let mut payload = Vec::new();
        # reader.read_to_end(&mut payload) ...
        # Read the rest of the data from the reader_for_payload into payload
        try:
            # The reader_for_payload is either BoundedAsyncReader or AsyncZlibDecoder.
            # Both should provide the remaining bytes of the packet payload.
            # BoundedAsyncReader will stop at the packet_len limit.
            # AsyncZlibDecoder will decompress until the end of the compressed stream within the bounded reader.
            # We need to read all remaining data from reader_for_payload.
            # Use read(-1) which reads until EOF of the reader_for_payload.
            payload = await reader_for_payload.read(-1) # Read until EOF of the reader_for_payload

        except Exception as err:
            # map_err(|err| PacketDecodeError::FailedDecompression(err.to_string()))?
            # This error mapping is slightly confusing in the Rust code. It maps the error from
            # `read_to_end` (which could be an IO error or a decompression error from the underlying reader)
            # specifically to `FailedDecompression`. Let's follow that.
            raise FailedDecompressionError(str(err))

        # Ok(RawPacket { id: packet_id, payload: payload.into(), })
        return RawPacket(id=packet_id, payload=payload)


# Helper functions for tests (equivalent to Rust's test helpers)

# Need equivalent of crate::ser::NetworkWriteExt
class NetworkWriteExt:
    def __init__(self, writer: io.BytesIO):
        self._writer = writer

    def write_var_int(self, varint: VarInt):
        varint.encode(self._writer)

    def write_slice(self, data: bytes):
        self._writer.write(data)

# Helper function to compress data using zlib
def compress_zlib(data: bytes) -> bytes:
    # Rust uses flate2::write::ZlibEncoder with Compression::default()
    # Python's zlib.compress uses Z_DEFAULT_COMPRESSION (-1) by default, which is equivalent.
    return zlib.compress(data)

# Helper function to encrypt data using AES-128 CFB-8 mode
def encrypt_aes128(data: bytearray, key: bytes, iv: bytes):
    # Rust uses cfb8::Encryptor::new_from_slices and encrypt()
    # Python's cryptography uses Cipher and decryptor/encryptor objects.
    # We need an encryptor here.
    # The Rust encrypt() method modifies the buffer in place.
    # The cryptography encryptor.update() returns bytes. We need to replace the data in the bytearray.
    if len(key) != 16 or len(iv) != 16:
        raise ValueError("Key and IV must be 16 bytes for AES-128 CFB-8")

    cipher = Cipher(algorithms.AES(key), modes.CFB8(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # Process data in chunks if necessary, or all at once
    encrypted_data = encryptor.update(data) + encryptor.finalize()

    # Replace the original data in the bytearray
    # Ensure the encrypted data length matches the original data length for CFB8
    if len(encrypted_data) != len(data):
         # This should not happen with CFB8 unless there's an issue
         raise RuntimeError("Encryption output length mismatch")

    # Modify the bytearray in place
    data[:] = encrypted_data


# Helper function to build a packet with optional compression and encryption
def build_packet(
    packet_id: int,
    payload: bytes,
    compress: bool,
    key: Optional[bytes],
    iv: Optional[bytes],
) -> bytes:
    buffer = io.BytesIO()
    writer = NetworkWriteExt(buffer)

    if compress:
        # Create a buffer that includes `packet_id_varint` and payload
        data_to_compress_buffer = io.BytesIO()
        data_to_compress_writer = NetworkWriteExt(data_to_compress_buffer)

        packet_id_varint = VarInt(packet_id)
        data_to_compress_writer.write_var_int(packet_id_varint)
        data_to_compress_writer.write_slice(payload)

        data_to_compress = data_to_compress_buffer.getvalue()

        # Compress the combined data
        compressed_payload = compress_zlib(data_to_compress)
        data_len = len(data_to_compress) # This is the uncompressed size (packet_id VarInt + payload)
        data_len_varint = VarInt(data_len)

        # Write decompressed length VarInt and compressed data to the main buffer
        writer.write_var_int(data_len_varint)
        writer.write_slice(compressed_payload)
    else:
        # No compression; `data_len` is payload length (this comment seems slightly off based on Rust code)
        # In the uncompressed case, the packet structure is:
        # packet_len VarInt | packet_id VarInt | payload
        # The Rust code writes packet_id VarInt and payload directly to the buffer
        # that will be prefixed by packet_len.
        packet_id_varint = VarInt(packet_id)
        writer.write_var_int(packet_id_varint)
        writer.write_slice(payload)

    # Calculate packet length: length of buffer (which contains packet_id/decompressed_len + data)
    packet_data = buffer.getvalue()
    packet_len = len(packet_data)
    packet_len_varint = VarInt(packet_len)

    # Create a new buffer for the entire packet
    packet_buffer = io.BytesIO()
    packet_length_encoded_buffer = io.BytesIO()
    packet_len_varint.encode(packet_length_encoded_buffer)
    packet_length_encoded = packet_length_encoded_buffer.getvalue()

    packet_buffer.write(packet_length_encoded)
    packet_buffer.write(packet_data)

    packet_bytes = bytearray(packet_buffer.getvalue()) # Use bytearray for in-place encryption

    # Encrypt if key and IV are provided.
    if key is not None and iv is not None:
        # Encrypt the *entire* packet including the length prefix
        # This matches the Rust test helper's behavior `encrypt_aes128(&mut packet, k, v);`
        # where `packet` is the buffer containing length + data.
        encrypt_aes128(packet_bytes, key, iv)
        return bytes(packet_bytes)
    else:
        return bytes(packet_bytes)


# Translate tests using pytest-asyncio
import pytest

# Need to define MAX_PACKET_SIZE and MAX_PACKET_DATA_SIZE for tests if not global
# Already defined globally above.

# Need to define CompressionThreshold for tests
# Already defined globally above as int.

@pytest.mark.asyncio
async def test_decode_without_compression_and_encryption():
    # Sample packet data: packet_id = 1, payload = "Hello"
    packet_id = 1
    payload = b"Hello"

    # Build the packet without compression and encryption
    packet = build_packet(packet_id, payload, False, None, None)

    # Initialize the decoder without compression and encryption
    reader = create_stream_reader(packet)
    decoder = NetworkDecoder(reader)

    # Attempt to decode
    raw_packet = await decoder.get_raw_packet() # .expect("Decoding failed")

    assert raw_packet.id == packet_id
    assert raw_packet.payload == payload

@pytest.mark.asyncio
async def test_decode_with_compression():
    # Sample packet data: packet_id = 2, payload = "Hello, compressed world!"
    packet_id = 2
    payload = b"Hello, compressed world!"

    # Build the packet with compression enabled
    packet = build_packet(packet_id, payload, True, None, None)

    # Initialize the decoder with compression enabled
    reader = create_stream_reader(packet)
    decoder = NetworkDecoder(reader)
    # Larger than payload
    decoder.set_compression(1000)

    # Attempt to decode
    raw_packet = await decoder.get_raw_packet() # .expect("Decoding failed")

    assert raw_packet.id == packet_id
    assert raw_packet.payload == payload

@pytest.mark.asyncio
async def test_decode_with_encryption():
    # Sample packet data: packet_id = 3, payload = "Hello, encrypted world!"
    packet_id = 3
    payload = b"Hello, encrypted world!"

    # Define encryption key and IV
    key = b"\x00" * 16 # Example key

    # Build the packet with encryption enabled (no compression)
    packet = build_packet(packet_id, payload, False, key, key)

    # Initialize the decoder with encryption enabled
    reader = create_stream_reader(packet)
    decoder = NetworkDecoder(reader)
    decoder.set_encryption(key) # Rust uses key as IV for decryption

    # Attempt to decode
    raw_packet = await decoder.get_raw_packet() # .expect("Decoding failed")

    assert raw_packet.id == packet_id
    assert raw_packet.payload == payload

@pytest.mark.asyncio
async def test_decode_with_compression_and_encryption():
    # Sample packet data: packet_id = 4, payload = "Hello, compressed and encrypted world!"
    packet_id = 4
    payload = b"Hello, compressed and encrypted world!"

    # Define encryption key and IV
    key = b"\x01" * 16 # Example key
    iv = b"\x01" * 16 # Example IV

    # Build the packet with both compression and encryption enabled
    packet = build_packet(packet_id, payload, True, key, iv)

    # Initialize the decoder with both compression and encryption enabled
    reader = create_stream_reader(packet)
    decoder = NetworkDecoder(reader)
    decoder.set_compression(1000)
    decoder.set_encryption(key) # Rust uses key as IV for decryption

    # Attempt to decode
    raw_packet = await decoder.get_raw_packet() # .expect("Decoding failed")

    assert raw_packet.id == packet_id
    assert raw_packet.payload == payload

@pytest.mark.asyncio
async def test_decode_with_invalid_compressed_data():
    # Sample packet data: packet_id = 5, payload_len = 10, but compressed data is invalid
    data_len = 10 # Expected decompressed size
    invalid_compressed_data = b"\xFF\xFF\xFF" # Invalid Zlib data

    # Build the packet with compression enabled but invalid compressed data
    # Structure: packet_len VarInt | decompressed_len VarInt | compressed_data
    buffer = io.BytesIO()
    writer = NetworkWriteExt(buffer)

    data_len_varint = VarInt(data_len)
    writer.write_var_int(data_len_varint)
    writer.write_slice(invalid_compressed_data)

    packet_data = buffer.getvalue()
    packet_len = len(packet_data)
    packet_len_varint = VarInt(packet_len)

    packet_buffer = io.BytesIO()
    packet_buffer.write(VarInt(packet_len).encode(io.BytesIO()).getvalue()) # Encode packet_len
    packet_buffer.write(packet_data)

    packet_bytes = packet_buffer.getvalue()

    # Initialize the decoder with compression enabled
    reader = create_stream_reader(packet_bytes)
    decoder = NetworkDecoder(reader)
    decoder.set_compression(1000)

    # Attempt to decode and expect a decompression error
    # let result = decoder.get_raw_packet().await;
    # if result.is_ok() { panic!("This should have errored!"); }
    with pytest.raises(FailedDecompressionError):
        await decoder.get_raw_packet()

@pytest.mark.asyncio
async def test_decode_with_zero_length_packet():
    # Sample packet data: packet_id = 7, payload = "" (empty)
    packet_id = 7
    payload = b""

    # Build the packet without compression and encryption
    packet = build_packet(packet_id, payload, False, None, None)

    # Initialize the decoder without compression and encryption
    reader = create_stream_reader(packet)
    decoder = NetworkDecoder(reader)

    # Attempt to decode and expect a read error (Rust comment says read error, but it should succeed)
    # The Rust test asserts success and checks the packet. Let's follow the assertion.
    raw_packet = await decoder.get_raw_packet() # .unwrap()
    assert raw_packet.id == packet_id
    assert raw_packet.payload == payload

@pytest.mark.asyncio
async def test_decode_with_maximum_length_packet():
    # Sample packet data: packet_id = 8, payload = "A" repeated (MAX_PACKET_DATA_SIZE - VarInt(8).written_size()) times
    # The Rust test comment says MAX_PACKET_SIZE times, but the code uses MAX_PACKET_SIZE - 1.
    # The payload size is chosen such that the total uncompressed size (VarInt(id) + payload)
    # equals MAX_PACKET_DATA_SIZE. VarInt(8) is 1 byte.
    # So total decompressed size is 1 + (MAX_PACKET_DATA_SIZE - 1) = MAX_PACKET_DATA_SIZE.
    # This should be compared against MAX_PACKET_DATA_SIZE.
    # The Rust test sets compression threshold to MAX_PACKET_SIZE + 1, ensuring compression is used
    # if the uncompressed size exceeds this threshold.
    # Our uncompressed size is MAX_PACKET_DATA_SIZE. If MAX_PACKET_DATA_SIZE > MAX_PACKET_SIZE + 1,
    # and the packet wasn't compressed, it would fail. But we build it compressed.
    # The threshold check `uncompressed_packet_size > threshold` is only relevant when `decompressed_length == 0`.
    # In this test, `decompressed_length` will be `MAX_PACKET_DATA_SIZE`, which is > 0.
    # So the threshold check `if raw_packet_length > threshold` is skipped.
    # The relevant checks are `packet_len <= MAX_PACKET_SIZE` and `decompressed_length <= MAX_PACKET_DATA_SIZE`.
    # The test builds a compressed packet where decompressed_length is MAX_PACKET_DATA_SIZE.
    # This should pass the `decompressed_length <= MAX_PACKET_DATA_SIZE` check.
    # The compressed packet length (packet_len) should be less than MAX_PACKET_SIZE
    # due to compression, thus passing the `packet_len <= MAX_PACKET_SIZE` check.

    packet_id = 8
    # Payload size such that VarInt(id) + payload size == MAX_PACKET_DATA_SIZE
    # VarInt(8) is 1 byte.
    payload_size = MAX_PACKET_DATA_SIZE - VarInt(packet_id).written_size()
    payload = b"\x41" * payload_size # "A" repeated

    # Build the packet with compression enabled
    packet = build_packet(packet_id, payload, True, None, None)
    # print(f"Built packet (with compression, maximum length): {packet!r}") # Rust debug print

    # Initialize the decoder with compression enabled
    reader = create_stream_reader(packet)
    decoder = NetworkDecoder(reader)
    # Rust uses MAX_PACKET_SIZE as usize + 1 for threshold. Let's use MAX_PACKET_SIZE + 1.
    decoder.set_compression(MAX_PACKET_SIZE + 1)

    # Attempt to decode
    result = await decoder.get_raw_packet() # .unwrap()

    raw_packet = result
    assert raw_packet.id == packet_id
    assert raw_packet.payload == payload
