# Better order:
from .db import DBManager
from .project import *      # Depends on Patient  
from .patient import *      # Base entity
from .study import *        # Depends on Patient
from .series import *       # Depends on Study
from .image_instance import * # Depends on Series
from .creator import *      # Independent
from .form_annotation import * # Depends on Patient, Study, ImageInstance
from .task import *         # Depends on ImageInstance, Creator
from .tag import *          # Depends on Annotation, Study, ImageInstance
from .annotation import *   # Depends on Patient, Study, Series, ImageInstance, Creator~