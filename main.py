import asyncio
import signal

# Define the client handler coroutine
async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')  # Get the client address
    print(f"New connection from {addr}")

    # Receive data asynchronously
    data = await reader.read(100)  # Read up to 100 bytes from the client
    message = data.decode()  # Decode the data to a string
    print(f"Received: {message}")

    # Send data back to the client asynchronously
    response = f"Hello {addr}, you sent: {message}"
    writer.write(response.encode())  # Write the response to the client
    await writer.drain()  # Ensure the data is actually sent

    print(f"Closing connection with {addr}")
    writer.close()  # Close the connection to the client
    await writer.wait_closed()  # Wait for the connection to be closed

# Define the main server function
async def main():
    # Start the server
    server = await asyncio.start_server(
        handle_client, '127.0.0.1', 8888)  # Listen on localhost and port 8888

    addr = server.sockets[0].getsockname()
    print(f"Server started on {addr}")

    # Run the server indefinitely, accepting connections and handling them
    async with server:
        await server.serve_forever()

# Graceful shutdown function for handling KeyboardInterrupt
def shutdown(signal, loop):
    print("Received shutdown signal. Shutting down gracefully...")
    for task in asyncio.Task.all_tasks(loop=loop):
        task.cancel()

    loop.stop()

# Run the event loop and handle keyboard interrupt
def run():
    loop = asyncio.get_event_loop()

    # Set up the signal handler for graceful shutdown
    loop.add_signal_handler(signal.SIGINT, shutdown, signal.SIGINT, loop)

    try:
        # Start the server
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
    finally:
        print("Server has been shut down.")

# Run the program
run()

