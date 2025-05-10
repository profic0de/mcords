import os
import time
from datetime import datetime

class Logger:
    def __init__(self, thread_name="Server thread", output_levels=("PRINT", "INFO", "WARN", "ERROR"), log_to_file=True, logs_folder="logs", parent_logger=None):
        self.thread_name = thread_name
        self.output_levels = set(level.upper() for level in output_levels)
        self.log_to_file = log_to_file
        self.logs_folder = logs_folder
        self.parent_logger = parent_logger  # For global logger
        self.log_file = None

        if self.parent_logger is None:
            self._setup_logs_folder()

    def _setup_logs_folder(self):
        if not os.path.exists(self.logs_folder):
            os.makedirs(self.logs_folder)

        latest_log = os.path.join(self.logs_folder, "latest.log")

        if os.path.exists(latest_log):
            date_str = datetime.now().strftime("%Y-%m-%d")
            idx = 1
            while True:
                rotated_log = os.path.join(self.logs_folder, f"server-{date_str}-{idx}.log")
                if not os.path.exists(rotated_log):
                    os.rename(latest_log, rotated_log)
                    break
                idx += 1

        self.log_file = latest_log
        open(self.log_file, 'w', encoding='utf-8').close()

    def _current_time(self):
        return time.strftime("%H:%M:%S")

    def _format_message(self, level, *args):
        timestamp = self._current_time()
        return f"[{timestamp}] [{self.thread_name}/{level.upper()}]: " + ' '.join(str(arg) for arg in args)

    def _write(self, message):
        if self.parent_logger:
            self.parent_logger._write(message)  # Delegate writing to the parent logger
        else:
            if self.log_to_file and self.log_file:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(message + '\n')

    def log(self, level, *args):
        level = level.upper()
        message = self._format_message(level, *args)

        # Printing to console: based on *self* output_levels
        if level in self.output_levels or "ALL" in self.output_levels:
            print(message)

        # Writing to file: always use the top parent
        if self.parent_logger:
            self.parent_logger._write(message)
        else:
            self._write(message)

    def info(self, *args):
        self.log("INFO", *args)

    def warn(self, *args):
        self.log("WARN", *args)

    def error(self, *args):
        self.log("ERROR", *args)

    def debug(self, *args):
        self.log("DEBUG", *args)

    def set_thread(self, thread_name):
        self.thread_name = thread_name

    def create_sub_logger(self, thread_name, output_levels=None):
        return Logger(
            thread_name=thread_name,
            output_levels=output_levels or self.output_levels,
            log_to_file=self.log_to_file,
            logs_folder=self.logs_folder,
            parent_logger=self if self.parent_logger is None else self.parent_logger
        )

logger = Logger(thread_name="main", output_levels=("INFO", "WARN", "ERROR"), log_to_file=False)