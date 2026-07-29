"""Search query construction, as a package.

Public surface via ``__all__``: ``SearchRepository``, the two condition carriers,
and the entity aliases (imported by ``server/services/search/fields`` -- the one
definition the entity-partitioning compares against by identity). The
``exists``/``selects`` builders are internal by omission; nothing outside this
package should import them.
"""
from .aliases import (
    ActiveFormAnnotation,
    ActiveSegmentation,
    FormCreator,
    FormTag,
    InstTag,
    SegCreator,
    SegTag,
    StudyTag,
)
from .conditions import AttributeConditionSpec, ResolvedCondition
from .repository import SearchRepository

__all__ = [
    "SearchRepository",
    "ResolvedCondition",
    "AttributeConditionSpec",
    "ActiveSegmentation",
    "ActiveFormAnnotation",
    "SegCreator",
    "FormCreator",
    "SegTag",
    "FormTag",
    "InstTag",
    "StudyTag",
]
