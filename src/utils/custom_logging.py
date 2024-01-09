import logging
from typing import Optional

from google.cloud import logging as gcp_logging

from src.utils import constants


class Logger(logging.Logger):
    # used to avoid too much verbosity from third-party libraries
    DEBUG = logging.DEBUG + 1

    def __init__(self, name: str) -> None:
        super().__init__(name)

    @classmethod
    def from_super(cls, super_instance: logging.Logger):
        # Create a new instance of Logger
        instance = cls(super_instance.name)
        # Copy the state from the superclass instance
        instance.__dict__.update(super_instance.__dict__)
        return instance

    def debug(self, msg: str, *args, **kwargs) -> None:
        super().log(Logger.DEBUG, msg, *args, **kwargs)


def setup_logging(name: Optional[str] = None) -> Logger:
    level = logging.getLevelName(constants.LOG_LEVEL)
    if level == logging.DEBUG:
        level = Logger.DEBUG

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

    logger = logging.getLogger(name)
    return Logger.from_super(logger)
