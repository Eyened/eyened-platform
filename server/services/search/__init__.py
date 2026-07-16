"""Search: the one non-CRUD service.

Search maps to a query language rather than a model, so it carries a vocabulary
(``fields``) and a DSL (``conditions``) that the CRUD services have no analogue
for. ``__all__`` is the real public surface -- ``conditions`` is internal by
omission.
"""
from .fields import (
    SignatureField,
    instance_order_by_fields,
    operators,
    searchable_fields,
    study_order_by_fields,
    study_searchable_fields,
)

__all__ = [
    "SignatureField",
    "instance_order_by_fields",
    "operators",
    "searchable_fields",
    "study_order_by_fields",
    "study_searchable_fields",
]
