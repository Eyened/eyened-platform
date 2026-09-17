"""Import cv2 before pytest-cov starts coverage. Loaded by ``-p _cov_cv2`` in pyproject.toml.

cv2's bootstrap() pops each native submodule out of sys.modules, re-imports the
Python stub and copies the native attributes across. With coverage already
active the native ``cv2.dnn`` is not in sys.modules when it is popped, so
nothing is copied, ``cv2.dnn.DictValue`` is missing, and every ``--cov`` run
dies importing ``eyened_orm.image_instance``. A root conftest.py cannot do this:
pytest-cov starts coverage before any conftest is imported, while ``-p``
plugins are imported earlier still.
"""
import cv2  # noqa: F401
