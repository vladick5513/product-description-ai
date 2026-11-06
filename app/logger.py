import logging
import sys

from app.settings import settings

logger = logging.getLogger("product_description_ai")
logger.setLevel(settings.LOG_LEVEL)

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_handler)
logger.propagate = False
