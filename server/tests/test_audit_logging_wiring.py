import logging
import sys

import pytest


@pytest.fixture(autouse=True)
def _restore_audit_logger():
    """configure_audit_logging() mutates the global eyened.audit logger; restore it
    so this test does not leak propagate=False / a stdout handler into other tests
    (notably the caplog-based tests in test_audit_service.py)."""
    audit = logging.getLogger("eyened.audit")
    saved = (audit.propagate, audit.handlers[:], audit.level)
    yield
    audit.propagate, audit.handlers, audit.level = saved


def test_audit_logger_writes_json_to_stdout_and_does_not_propagate():
    """configure_audit_logging() attaches a stdout StreamHandler and isolates the logger."""
    from server.main import configure_audit_logging

    configure_audit_logging()
    audit = logging.getLogger("eyened.audit")

    assert audit.propagate is False
    stream_handlers = [h for h in audit.handlers
                       if isinstance(h, logging.StreamHandler)]
    assert stream_handlers, "expected a StreamHandler on eyened.audit"
    assert any(getattr(h, "stream", None) is sys.stdout for h in stream_handlers)
