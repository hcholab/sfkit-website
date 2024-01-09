import logging
import os
from typing import Optional
from google.cloud import logging as gcp_logging

from src.utils import constants


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    # If the environment variable is set to "True", we are running on Cloud Run
    if os.environ.get("CLOUD_RUN", "False").lower() == "true":
        # Instantiate the Google Cloud Logging client
        client = gcp_logging.Client()

        # Attach the Cloud Logging handler to the root logger
        client.get_default_handler()
        client.setup_logging(log_level=logging.getLevelName(constants.LOG_LEVEL))
    else:
        # For local development, log to stdout with a simple format
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    return logging.getLogger(name)
