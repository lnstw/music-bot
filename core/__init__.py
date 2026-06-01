import logging
from core.log import setup_logging
setup_logging()
logging.basicConfig(level=logging.INFO)
logging.info("Service 載入")