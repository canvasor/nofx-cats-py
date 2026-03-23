import logging

from cats_py.infra.logging import configure_logging


def test_configure_logging_suppresses_httpx_info_noise() -> None:
    configure_logging("test.logging", log_level="INFO")

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
