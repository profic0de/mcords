import os
import sys
import shutil
import msvcrt
import ctypes

class Console:
    def __init__(self):
        self.lines = []  # Stored printed lines
        self.input_line = ''  # Current input line
        self.console_width, self.console_height = shutil.get_terminal_size()
        self.console_handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE

    def get_terminal_height(self):
        return self.console_height

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    def move_cursor(self, x, y):
        # Create an instance of the COORD class with (x, y)
        coord = self.COORD(x, y)
        ctypes.windll.kernel32.SetConsoleCursorPosition(self.console_handle, coord)

    def refresh(self, prompt='> '):
        # Calculate the available space for printed lines (excluding input)
        height = self.get_terminal_height()
        max_output_lines = height - 1  # Reserve the last line for input prompt

        visible_lines = self.lines[-max_output_lines:]

        # Move the cursor to the top to overwrite content
        self.move_cursor(0, 0)
        
        # Print visible lines in the console
        for line in visible_lines:
            print(line)

        # Move cursor to the bottom where the input will go
        self.move_cursor(0, height - 1)

        # Print input line at the bottom (overwrite it)
        print(prompt + self.input_line, end='', flush=True)

    def print(self, text):
        self.lines.append(text)
        self.refresh()

    def input(self, prompt='> '):
        self.input_line = ''
        self.refresh(prompt)

        while True:
            if msvcrt.kbhit():
                byte = msvcrt.getch()
                
                if byte == b'\r':  # Enter key
                    entered_text = self.input_line
                    self.lines.append(prompt + entered_text)
                    self.input_line = ''
                    self.refresh(prompt)
                    return entered_text
                elif byte in (b'\x08',):  # Backspace key
                    if self.input_line:
                        self.input_line = self.input_line[:-1]
                        self.refresh(prompt)
                elif byte in (b'\xe0', b'\x00'):  
                    msvcrt.getch()  # Special keys (skip second byte)
                else:
                    char = byte.decode('utf-8', errors='ignore')
                    self.input_line += char
                    self.refresh(prompt)

# Example usage:
console = Console()

console.print("Hello, Windows!")
console.print("Another line.")

while True:
    user_input = console.input("Say something: ")
    console.print(f"You said: {user_input}")
