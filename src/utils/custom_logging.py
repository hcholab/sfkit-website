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

    def debug(self, msg: object, *args, **kwargs) -> None:
        super().log(Logger.DEBUG, msg, *args, **kwargs)


logging.addLevelName(Logger.DEBUG, "DEBUG")


def setup_logging(name: Optional[str] = None) -> Logger:
    level = logging.getLevelName(constants.LOG_LEVEL)
    if level == logging.DEBUG:
        level = Logger.DEBUG

    if constants.CLOUD_RUN.lower() == "true":
        client = gcp_logging.Client()
        client.setup_logging(log_level=level)
        logger = logging.getLogger()
        print(f"Initial logging handlers: {logger.handlers}", flush=True)
        logger.handlers = list({h for h in logger.handlers if is_cloud_run_handler(h)})
    else:
        # For Kubernetes or local development, log to stdout with a simple format
        logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        logger = logging.getLogger(name)
        logger.handlers = list(set(logger.handlers))
    return Logger.from_super(logger)


def is_cloud_run_handler(handler: logging.Handler) -> bool:
    """
    is_cloud_handler

    Returns True or False depending on whether the input is a
    google-cloud-logging handler class

    """
    accepted_handlers = (
        gcp_logging.handlers.StructuredLogHandler,
        gcp_logging.handlers.CloudLoggingHandler,
    )
    return isinstance(handler, accepted_handlers)
