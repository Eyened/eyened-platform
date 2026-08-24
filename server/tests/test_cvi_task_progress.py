from server.routes.task import _summarize_cvi_statuses


def test_summarize_cvi_statuses_counts_ready_only():
    rows = [
        {"status": "Ready"},
        {"status": "Busy"},
        {"status": "Not Started"},
        {"status": "ready"},
        {"status": None},
        {"status": ""},
    ]

    total, ready = _summarize_cvi_statuses(rows)

    assert total == 6
    assert ready == 2


def test_summarize_cvi_statuses_handles_missing_status_column():
    assert _summarize_cvi_statuses([]) == (0, 0)
    assert _summarize_cvi_statuses(None) == (0, 0)
