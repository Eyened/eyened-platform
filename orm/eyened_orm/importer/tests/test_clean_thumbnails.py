"""Unit tests for thumbnail FS/DB cleanup helpers (no live database required)."""

from __future__ import annotations

from pathlib import Path

from eyened_orm.importer.thumbnails import (
    THUMBNAIL_SIZES,
    delete_thumbnail_files,
    find_broken_thumbnail_refs,
    find_dangling_thumbnail_files,
    parse_thumbnail_relative_path,
    thumbnail_filename,
)


def _touch(folder: Path, relative: str) -> Path:
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jpg")
    return path


def test_parse_thumbnail_relative_path():
    assert parse_thumbnail_relative_path("3/ab/uuid_144.jpg") == ("3/ab/uuid", 144)
    assert parse_thumbnail_relative_path("3/ab/uuid_540.jpg") == ("3/ab/uuid", 540)
    assert parse_thumbnail_relative_path("uuid_999.jpg") is None
    assert parse_thumbnail_relative_path("_144.jpg") is None
    assert parse_thumbnail_relative_path("notes.txt") is None


def test_find_dangling_thumbnail_files(tmp_path: Path):
    folder = tmp_path / "thumbnails"
    indexed = "1/aa/live"
    orphan = "1/aa/orphan"
    _touch(folder, thumbnail_filename(indexed, 144))
    _touch(folder, thumbnail_filename(indexed, 540))
    orphan_144 = _touch(folder, thumbnail_filename(orphan, 144))
    orphan_540 = _touch(folder, thumbnail_filename(orphan, 540))
    _touch(folder, "1/aa/readme.txt")  # ignored (not a known size jpg)

    dangling, scanned = find_dangling_thumbnail_files(folder, {indexed})
    assert scanned == 4
    assert dangling == [orphan_144, orphan_540]


def test_find_broken_thumbnail_refs(tmp_path: Path):
    folder = tmp_path / "thumbnails"
    complete = "2/bb/complete"
    partial = "2/bb/partial"
    missing = "2/bb/missing"
    _touch(folder, thumbnail_filename(complete, 144))
    _touch(folder, thumbnail_filename(complete, 540))
    _touch(folder, thumbnail_filename(partial, 144))

    indexed = {
        complete: [10],
        partial: [20, 21],
        missing: [30],
    }
    broken = find_broken_thumbnail_refs(folder, indexed)
    assert [(b.image_instance_id, b.thumbnail_path, b.missing_sizes) for b in broken] == [
        (30, missing, THUMBNAIL_SIZES),
        (20, partial, (540,)),
        (21, partial, (540,)),
    ]


def test_delete_thumbnail_files_prunes_empty_dirs(tmp_path: Path):
    folder = tmp_path / "thumbnails"
    keep = _touch(folder, thumbnail_filename("1/aa/keep", 144))
    remove = _touch(folder, thumbnail_filename("1/bb/gone", 144))

    deleted = delete_thumbnail_files([remove], folder=folder)
    assert deleted == [remove]
    assert not remove.exists()
    assert keep.exists()
    assert not (folder / "1" / "bb").exists()
    assert (folder / "1" / "aa").is_dir()
