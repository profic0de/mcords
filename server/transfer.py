if __name__ != "__main__": from server.packet.build import Build
import dns.resolver

def resolve_minecraft_srv(domain: str) -> tuple[str, int]:
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

    try:
        answers = resolver.resolve(f"_minecraft._tcp.{domain}", "SRV")
        for rdata in answers:
            return str(rdata.target).rstrip('.'), rdata.port
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return domain, 25565
    except dns.resolver.LifetimeTimeout:
        print("DNS resolution timed out. Try a different network or DNS server.")
        return domain, 25565

# print(resolve_minecraft_srv("frontrooms.joinserver.ru"))

from mcstatus import JavaServer

def ping_minecraft_server(data) -> dict:
    try:
        server = JavaServer(data[0], data[1])
        status = server.status()
        
        return {
            # "motd": status.description,  # Server MOTD
            "players_online": status.players.max,  # Online player count
            # "version": status.version.protocol,  # Minecraft version
            # "latency": server.ping()  # Server latency in ms
        }
    except Exception as e:
        return {"error": f"Failed to ping server: {e}"}

# Example usage:
# print(ping_minecraft_server(resolve_minecraft_srv("play.pvplegacy.net")))

class Transfer:
    async def to(player, ip):
        ip, port = resolve_minecraft_srv(ip)
        # print(ip,port)
        async with Build(0x71, player) as build:
            build.string("mcords:cookie")
            build.array(f"{ip}:{port}".encode(),build.byte)

        async with Build(0x7a, player) as build:
            build.string("127.0.0.1")
            build.varint(25568)
            