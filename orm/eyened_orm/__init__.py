# Better order:
from .db import Database  # noqa: F401
from .project import *      # Depends on Patient  # noqa: F403
from .patient import *      # Base entity  # noqa: F403
from .study import *        # Depends on Patient  # noqa: F403
from .series import *       # Depends on Study  # noqa: F403
from .image_instance import * # Depends on Series  # noqa: F403
from .creator import *      # Independent  # noqa: F403
from .form_annotation import * # Depends on Patient, Study, ImageInstance  # noqa: F403
from .task import *         # Depends on ImageInstance, Creator  # noqa: F403
from .tag import *          # Depends on Annotation, Study, ImageInstance  # noqa: F403
from .annotation import *   # Depends on Patient, Study, Series, ImageInstance, Creator~  # noqa: F403
from .segmentation import * # Depends on ImageInstance, Feature, Creator, SubTask  # noqa: F403
from .attributes import *   # Depends on Model, ImageInstance  # noqa: F403
