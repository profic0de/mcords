from Crypto.Cipher import PKCS1_v1_5, AES
from server.packet.build import Build
from server.packet.parse import Parse
from Crypto.PublicKey import RSA
from server.player import Player
from server.world import logger
from server.world.engine import JoinGameError
import requests, hashlib, os
from server.vars import Var

async def login(player:Player, online_mode=True, compression = -1):
    logger.debug(f"⚙️ Step 1: Receive Login Start")
    # Step 1: Receive Login Start
    with Parse(await player.packet.recv()) as parse:
        packet_id = parse.varint()
        username = parse.string()

    if packet_id != 0x00:
        raise JoinGameError("Expected Login Start")

    if compression > 0:
        async with Build(0x03, player) as build:
            build.varint(compression)
        player.packet.set_compression(compression)

    logger.debug(f"🔓 Login Start received for username: {username}")
    player.username = username

    if online_mode == False:
        player.uuid = Var.get_offline_uuid(username)
        async with Build(0x02, player) as build:
            build.raw(bytes.fromhex(player.uuid.replace('-', '')))
            build.string(username)
            build.varint(0)


        with Parse(await player.packet.recv()) as parse:
            packet_id = parse.varint()
        # print(f"📦 Received packet: ID: {packet_id:02X}")

        if packet_id == 0x03:
            logger.debug("✅ Login Success")
        else:
            raise JoinGameError(f"Login error")
        
        player.state = "config"
        return

    logger.debug(f"⚙️ Step 2: Generate RSA keypair and verify token")
    # Step 2: Generate RSA keypair and verify token
    rsa_key = RSA.generate(1024)
    public_key = rsa_key.publickey().export_key(format='DER')
    verify_token = os.urandom(16)

    logger.debug(f"⚙️ Step 3: Send Encryption Request")
    # Step 3: Send Encryption Request
    async with Build(0x01, player) as build:
        build.string("")
        build.varint(len(public_key)); build.raw(public_key)
        build.varint(len(verify_token)); build.raw(verify_token)
        build.bool(True)

    logger.debug(f"⚙️ Step 4: Receive Encryption Response")
    # Step 4: Receive Encryption Response
    with Parse(await player.packet.recv()) as parse:
        packet_id = parse.varint()
        secret = parse.array(parse.byte)
        token = parse.array(parse.byte)

    if packet_id != 0x01:
        raise JoinGameError("Expected Encryption Response")

    logger.debug(f"⚙️ Step 5: Decrypt shared secret and verify token")
    # Step 5: Decrypt shared secret and verify token
    cipher = PKCS1_v1_5.new(rsa_key)
    shared_secret = cipher.decrypt(secret, None)
    decrypted_token = cipher.decrypt(token, None)

    if decrypted_token != verify_token:
        raise JoinGameError("Verify token mismatch")

    logger.debug(f"⚙️ Step 6: Mojang Authentication")
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
        raise JoinGameError("Mojang authentication failed")

    profile = resp.json()
    uuid = profile["id"]
    # name = profile["name"]

    # AES Encryption (Step 7)
    logger.debug(f"⚙️ Step 7: Enable AES encryption (correct initialization)")

    player.packet.set_encryption(shared_secret)

    # Verify Token Validation (Step 5)
    if decrypted_token != verify_token:
        raise JoinGameError("Verify token mismatch: Decrypted token does not match original")

    # Step 8: Send Login Success
    logger.debug("⚙️ Step 8: Send Login Success")

    # Player's UUID and Username
    player.uuid = profile["id"]  # Player's UUID as a 16-byte string
    player.username = profile["name"]
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
    async with Build(0x02, player) as build:
        build.raw(packet_data)

    # print(packet_data)

    with Parse(await player.packet.recv()) as parse:
        packet_id = parse.varint()

    if packet_id == 0x03:
        logger.debug("✅ Login Success")
    else:
        raise JoinGameError(f"Login error")
    
    player.state = "config"