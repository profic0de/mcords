import asyncio

# Simulate handling a client
async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    print(f"New connection from {addr}")

    # Example of receiving data asynchronously from the client
    data = await reader.read(100)  # Read up to 100 bytes of data
    message = data.decode()
    print(f"Received: {message}")

    # Send a response back to the client
    response = f"Hello {addr}, you sent: {message}"
    writer.write(response.encode())
    await writer.drain()  # Wait for the response to be sent

    print(f"Closing connection with {addr}")
    writer.close()
    await writer.wait_closed()

# Main function to start the server and accept clients
async def main():
    server = await asyncio.start_server(
        handle_client, '127.0.0.1', 8888)  # Listening on localhost and port 8888
    addr = server.sockets[0].getsockname()
    print(f"Server started on {addr}")

    # Run the server and handle incoming clients
    async with server:
        await server.serve_forever()

# Run the main function in the asyncio event loop
asyncio.run(main())
