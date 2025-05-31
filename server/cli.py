import asyncio
import sys
import readchar

class Console:
    def __init__(self, stop_event: asyncio.Event):
        self.input_buffer = ""
        self.stop_event = stop_event

    def redraw_prompt(self):
        prompt = colored("> ", "green")
        # if self.input_buffer == None: print("hi")
        line = prompt + self.input_buffer
        sys.stdout.write('\r\x1b[2K')
        sys.stdout.write(line)
        sys.stdout.flush()

    def print(self, text: str):
        sys.stdout.write('\r\x1b[2K')
        sys.stdout.write(text + '\n')
        self.redraw_prompt()

    async def input(self):
        while not self.stop_event.is_set():
            try:
                key = await asyncio.to_thread(readchar.readkey)
            except KeyboardInterrupt:
                self.stop_event.set()
                break

            if key == '\r':
                print()
                if self.input_buffer.strip().lower() == "help":
                    print(colored("--------------help------------------","cyan"))
                    print(f" {colored("help","green")}  - show this menu")
                    print(f"{colored("memory","green")} - show the RAM usage in MB")
                    print(f" {colored("cls","green")}   - clears the console")
                    print(colored("------------------------------------","cyan"))
                elif self.input_buffer.strip().lower() == "memory":
                    from server.blocks import memory_usage
                    print(f"Memory usage: {colored(f"{memory_usage():.2f} MB","cyan")}")
                elif self.input_buffer.strip().lower() == "cls":
                    from os import system, name
                    system('cls' if name == 'nt' else 'clear')
                else:
                    print(colored(f"Wrong command: {self.input_buffer}"))
                    print(colored(f"Type \"Help\" for help -_-"))
                self.input_buffer = ""
                self.redraw_prompt()
            elif key in ('\x7f', '\b'):
                self.input_buffer = self.input_buffer[:-1]
                self.redraw_prompt()
            elif key.isprintable():
                self.input_buffer += key
                self.redraw_prompt()

def colored(text, color="red"):
    colors = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "gray": "\033[90m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, colors['red'])}{text}{colors['reset']}"

