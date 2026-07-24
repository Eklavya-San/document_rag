import pytest
from app.config import Settings
from app.logging_config import setup_logging
from loguru import logger


def test_setup_logging_creates_log_file(tmp_path):
    log_file = tmp_path / "app.log"
    settings = Settings(log_file_path=str(log_file), log_level="DEBUG")
    setup_logging(settings)

    logger.info("Test loguru entry")

    assert log_file.exists()
    content = log_file.read_text()
    assert "Test loguru entry" in content
