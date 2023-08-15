import os
import logging
from unittest.mock import MagicMock, patch
from src.utils.custom_logging import setup_logging


def test_setup_logging_local():
    # Mock the environment variable
    with patch.dict(os.environ, {"CLOUD_RUN": "False"}):
        # Test the setup_logging function
        logger = setup_logging("test_logger_local")
        assert logger.name == "test_logger_local"
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.NOTSET  # Assert the logger level to be NOTSET


def test_setup_logging_cloud_run():
    # Mock the environment variable
    with patch.dict(os.environ, {"CLOUD_RUN": "True"}):
        # Mock the Google Cloud Logging client
        with patch("src.utils.custom_logging.gcp_logging.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Test the setup_logging function
            logger = setup_logging("test_logger_cloud_run")
            assert logger.name == "test_logger_cloud_run"
            assert isinstance(logger, logging.Logger)
            assert logger.level == logging.NOTSET  # Assert the logger level to be NOTSET

            # Assert the Google Cloud Logging client methods were called
            mock_client.assert_called_once()
            mock_client_instance.get_default_handler.assert_called_once()
            mock_client_instance.setup_logging.assert_called_once_with(log_level=logging.INFO)
