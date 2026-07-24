import pytest

from eyened_orm import Feature


def _drain(gen):
    """Advance a get_db-style generator past its post-yield finalization."""
    try:
        next(gen)
    except StopIteration:
        pass


def test_get_db_commits_on_clean_exit(SessionLocal):
    """A generator that adds a row and exits cleanly leaves the row committed."""
    from server.db import get_db

    # Bind get_db to the test engine for this check.
    def bound():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    gen = bound()
    s = next(gen)
    s.add(Feature(FeatureName="committed"))
    _drain(gen)

    with SessionLocal() as verify:
        assert verify.query(Feature).filter_by(FeatureName="committed").count() == 1


def test_get_db_rolls_back_and_reraises_on_exception(SessionLocal):
    """An exception thrown into the generator rolls the write back and propagates."""
    def bound():
        with SessionLocal() as s:
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise

    gen = bound()
    s = next(gen)
    s.add(Feature(FeatureName="doomed"))
    with pytest.raises(ValueError):
        gen.throw(ValueError("boom"))

    with SessionLocal() as verify:
        assert verify.query(Feature).filter_by(FeatureName="doomed").count() == 0
