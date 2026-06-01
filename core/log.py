import logging
class ColorizingStreamHandler(logging.StreamHandler):
    COLORS = {
        "INFO": "\033[0;32m",
        "WARNING": "\033[0;33m",
        "ERROR": "\033[0;31m",
        "CRITICAL": "\033[1;31m",
        "DEBUG": "\033[0;34m",
        "WHITE": "\033[0m",
    }
    def emit(self, record):
        msg = self.format(record)
        level_color = self.COLORS.get(record.levelname, self.COLORS["WHITE"])
        parts = msg.split(" - ", 1)
        if len(parts) < 2:
            self.stream.write(msg + "\n")
            return
        timestamp_part = parts[0]
        level_part = parts[1].split(":")[0]
        message_part = parts[1][len(level_part) + 1:]
        if record.levelname == "INFO":
            level_spacing = "     "
        elif record.levelname == "WARNING":
            level_spacing = "  "
        elif record.levelname == "ERROR":
            level_spacing = "    "
        elif record.levelname == "DEBUG":
            level_spacing = "    "
        else:
            level_spacing = " "
        colored_msg = f"{timestamp_part} - {level_color}{level_part}{ColorizingStreamHandler.COLORS['WHITE']}:{level_spacing}{message_part}"
        self.stream.write(f"{colored_msg}\n")
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = ColorizingStreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.addHandler(handler)
