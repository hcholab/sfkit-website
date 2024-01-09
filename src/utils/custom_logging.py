import logging
from typing import Optional

from google.cloud import logging as gcp_logging

from src.utils import constants


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    if constants.TERRA or constants.CLOUD_RUN.lower() == "true":
        # Instantiate the Google Cloud Logging client
        client = gcp_logging.Client()

        # Attach the Cloud Logging handler to the root logger
        client.get_default_handler()

        log_level = logging.getLevelName(constants.LOG_LEVEL)
        client.setup_logging(log_level=log_level)
        logging.log(logging.INFO, "Logging initialized, LOG_LEVEL=%s(%d)", constants.LOG_LEVEL, log_level)
    else:
        # For local development, log to stdout with a simple format
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    return logging.getLogger(name)
