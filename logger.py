import logging
import sys


# Create main logger
logger = logging.getLogger()
logger.setLevel(logging.ERROR)

# ---------------- File Handler ----------------
file_handler = logging.FileHandler("errors.log", mode="a")
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
))

# ---------------- Terminal Handler ----------------
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(logging.Formatter(
    "%(levelname)s - %(filename)s:%(lineno)d - %(message)s"
))

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)
