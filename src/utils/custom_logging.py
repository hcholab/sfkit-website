import logging
from typing import Optional

from google.cloud import logging as gcp_logging

from src.utils import constants


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    level = logging.getLevelName(constants.LOG_LEVEL)

    # If the environment variable is set to "True", we are running on Cloud Run
    if constants.CLOUD_RUN.lower() == "true":
        # Instantiate the Google Cloud Logging client
        client = gcp_logging.Client()

        # Attach the Cloud Logging handler to the root logger
        client.get_default_handler()
        client.setup_logging(log_level=level)
    else:
        # For Kubernetes or local development, log to stdout with a simple format
        logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    logging.log(logging.INFO, "Logging initialized, LOG_LEVEL=%s(%d)", constants.LOG_LEVEL, level)
    return logging.getLogger(name)
