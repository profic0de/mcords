import socket
import os
import hashlib
import json
import requests

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES

from server.vars import Var
from server.logger import logger

def login(self, online_mode=True):
    logger.debug(f"⚙️  Step 1: Receive Login Start")
    # Step 1: Receive Login Start
    packet_id, data = self.recv_packet()
    if packet_id != 0x00:
        raise Exception("Expected Login Start")

    name_len, offset = Var.read_varint_from_bytes(data)
    username = data[offset:offset + name_len].decode("utf-8")
    logger.debug(f"🔓 Login Start received for username: {username}")
    self.username = username

    if online_mode == False:
        self.uuid = Var.get_offline_uuid(username)
        packet_data = (
            bytes.fromhex(self.uuid.replace('-', '')) +
            Var.write_string(username) +
            # Var.write_varint(len(properties)) +
            Var.write_varint(0)  # 0 properties
        )
        self.send_packet(0x02, packet_data)

        packet_id, data = self.recv_packet()
        # print(f"📦 Received packet: ID: {packet_id:02X}")

        if packet_id == 0x03:
            logger.debug("✅ Login Success")
        else:
            raise Exception(f"Login error")
        return

    logger.debug(f"⚙️  Step 2: Generate RSA keypair and verify token")
    # Step 2: Generate RSA keypair and verify token
    rsa_key = RSA.generate(1024)
    public_key = rsa_key.publickey().export_key(format='DER')
    verify_token = os.urandom(16)



    logger.debug(f"⚙️  Step 3: Send Encryption Request")
    # Step 3: Send Encryption Request
    authenticate = True
    payload = (
        Var.write_string("") +
        Var.write_varint(len(public_key)) + public_key +
        Var.write_varint(len(verify_token)) + verify_token
        + b'\x01' if authenticate else b'\x00'
    )
    self.send_packet(0x01, payload)



    logger.debug(f"⚙️  Step 4: Receive Encryption Response")
    # Step 4: Receive Encryption Response
    packet_id, data = self.recv_packet()
    if packet_id != 0x01:
        raise Exception("Expected Encryption Response")

    secret, rest = Var.read_varint_bytes(data)
    token, _ = Var.read_varint_bytes(rest)



    logger.debug(f"⚙️  Step 5: Decrypt shared secret and verify token")
    # Step 5: Decrypt shared secret and verify token
    cipher = PKCS1_v1_5.new(rsa_key)
    shared_secret = cipher.decrypt(secret, None)
    decrypted_token = cipher.decrypt(token, None)

    if decrypted_token != verify_token:
        raise Exception("Verify token mismatch")



    logger.debug(f"⚙️  Step 6: Mojang Authentication")
    # Step 6: Mojang Authentication
    sha1 = hashlib.sha1()
    sha1.update(b"")  # empty server ID
    sha1.update(shared_secret)
    sha1.update(public_key)
    server_hash = Var.java_hex(sha1.digest())

    resp = requests.get(
        "https://sessionserver.mojang.com/session/minecraft/hasJoined",
        params={"username": username, "serverId": server_hash}
    )
    if resp.status_code != 200:
        raise Exception("Mojang authentication failed")

    profile = resp.json()
    uuid = profile["id"]
    # name = profile["name"]



    # AES Encryption (Step 7)
    logger.debug(f"⚙️  Step 7: Enable AES encryption (correct initialization)")
    iv = shared_secret
    self.encrypt_cipher = AES.new(shared_secret, AES.MODE_CFB, iv=iv, segment_size=8)
    self.decrypt_cipher = AES.new(shared_secret, AES.MODE_CFB, iv=iv, segment_size=8)

    self.encryption_enabled = True

    # Verify Token Validation (Step 5)
    if decrypted_token != verify_token:
        raise Exception("Verify token mismatch: Decrypted token does not match original")


    # Step 8: Send Login Success
    logger.debug("⚙️  Step 8: Send Login Success")

    # Player's UUID and Username
    self.uuid = profile["id"]  # Player's UUID as a 16-byte string
    self.username = profile["name"]
    # properties = profile.get("properties", [])

    # Encode properties
    
    properties = profile.get("properties", [])
    packet_data = (
        bytes.fromhex(uuid.replace('-', '')) +
        Var.write_string(username) +
        Var.write_varint(len(properties))
        # Var.write_varint(0)  # 0 properties
    )

    for prop in properties:
        name = prop["name"]
        value = prop["value"]
        signature = prop.get("signature")

        packet_data += Var.write_string(name)
        packet_data += Var.write_string(value)

        if signature:
            packet_data += b"\x01"  # has signature
            packet_data += Var.write_string(signature)
        else:
            packet_data += b"\x00"  # no signature


    # packet_data = b'l\xee\xb4M_q>\xbf\x84\x12\x9d2\x0f\xc0\xb0\xcf\tProficode\x00'
    # print(packet_data.hex())
    # Send the packet
    self.send_packet(0x02, packet_data)
    # print(packet_data)

    packet_id, data = self.recv_packet()
    # print(f"📦 Received packet: ID: {packet_id:02X}")

    if packet_id == 0x03:
        logger.debug("✅ Login Success")
    else:
        raise Exception(f"Login error")