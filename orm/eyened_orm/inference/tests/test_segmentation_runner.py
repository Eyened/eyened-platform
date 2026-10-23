"""Shared chunk/filter/run loop for segmentation CLI entrypoints."""

from __future__ import annotations

from eyened_orm.inference.segmentation_runner import run_segmentation_batches


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class _FakePipeline:
    def __init__(self, *, skip: set[int] | None = None) -> None:
        self.skip = skip or set()
        self.runs: list[set[int]] = []

    def filter_image_ids(self, image_ids):
        return set(image_ids) - self.skip

    def run(self, image_ids) -> None:
        self.runs.append(set(image_ids))


def test_run_segmentation_batches_filters_when_not_overwriting(monkeypatch, capsys):
    monkeypatch.setattr(
        "eyened_orm.commands.targets.iter_image_id_chunks",
        lambda ids: [[1, 2, 3]],
    )
    session = _FakeSession()
    pipeline = _FakePipeline(skip={2})

    total = run_segmentation_batches(
        session, {1, 2, 3}, pipeline, overwrite=False, commit_after_chunk=True
    )

    assert total == 2
    assert pipeline.runs == [{1, 3}]
    assert session.commits == 1
    assert "Completed processing 2 images" in capsys.readouterr().out


def test_run_segmentation_batches_skips_filter_when_overwriting(monkeypatch):
    monkeypatch.setattr(
        "eyened_orm.commands.targets.iter_image_id_chunks",
        lambda ids: [list(ids)],
    )
    pipeline = _FakePipeline(skip={99})

    total = run_segmentation_batches(
        _FakeSession(), {1}, pipeline, overwrite=True, commit_after_chunk=False
    )

    assert total == 1
    assert pipeline.runs == [{1}]


def test_run_segmentation_batches_empty_input_prints_no_images(capsys):
    pipeline = _FakePipeline()

    total = run_segmentation_batches(
        _FakeSession(), set(), pipeline, overwrite=False
    )

    assert total == 0
    assert pipeline.runs == []
    out = capsys.readouterr().out
    assert "No images to process" in out


def test_run_segmentation_batches_skips_empty_chunks_after_filter(monkeypatch, capsys):
    monkeypatch.setattr(
        "eyened_orm.commands.targets.iter_image_id_chunks",
        lambda ids: [[1], [2]],
    )
    pipeline = _FakePipeline(skip={1, 2})

    total = run_segmentation_batches(
        _FakeSession(), {1, 2}, pipeline, overwrite=False
    )

    assert total == 0
    assert pipeline.runs == []
    assert "No images to process" in capsys.readouterr().out
