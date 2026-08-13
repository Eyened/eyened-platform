"""Every read of a project-scoped entity consults the caller's scope.

The rejected ORM-level ``do_orm_execute`` listener would have given this
structurally -- filtering would fire however a statement was built. Explicit
scoping trades that for legibility and for a predicate that does not silently
change what a query means; the cost is that a method written later can forget,
and this test is what stops it shipping.

Not to be confused with ``orm/eyened_orm/tests/test_repository_read_scoping.py``,
which pins read *behaviour* one method at a time. This file is the coverage
complement: it fails on omission, never on behaviour, and it must never be
merged into or overwritten by that one.

Scope, stated so the guard is not over-trusted: it checks that a method's body
calls ``apply_scope``/``scoped_one``, or is one of the few allow-listed methods
that *consume* ``self._scope`` by hand, not that the argument is the right
entity. Review is the backstop for that.

The DTO detector below has its own, narrower blind spot: it matches only a
bare-``Name`` call to ``object_session(...)`` and a parameter annotated
literally ``Session``, so ``sa.orm.object_session(x)`` (attribute form) or a
converter that reads through an injected repository instead of a raw session
would not be found. That boundary is acceptable -- the pin is a ratchet on a
known-open surface, not a completeness claim -- but it is not exercised by
this guard, so it is not caught either.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_REPOSITORIES = _ROOT / "orm" / "eyened_orm" / "repositories"
_DTOS = _ROOT / "server" / "dtos"

# Repositories over entities with no project anchor. Adding a name here is a
# claim that the entity is not project data; each one is justified.
_UNSCOPED_REPOSITORIES = {
    "CreatorRepository",  # identity table, not project data
    "DeviceRepository",  # device catalogue, shared across projects
    "FormSchemaRepository",  # form definitions, shared across projects
    "TagRepository",  # a Tag is a label; the *link* is what sits in a project
    "ProjectMemberRepository",  # builds the scope rather than consuming it
}

# Read methods on scoped repositories that deliberately do not filter.
_UNSCOPED_METHODS = {
    "StudyRepository.get_tag": "returns a Tag, not a Study; a label carries no project",
    # FeatureRepository is exempt per *method*, not as a class. "Annotation
    # vocabulary" is true of these four -- a Feature and its composite links
    # carry no project -- and was false of segmentation_counts, which counts
    # project data and IS scoped. A class-wide entry cannot tell them apart: it
    # skips before any method is inspected, so nothing here was ever scanned
    # and _EXPECTED_SCANNED_READS never moved.
    "FeatureRepository.get_by_id": "annotation vocabulary; a Feature carries no project",
    "FeatureRepository.list_all": "annotation vocabulary",
    "FeatureRepository.parent_names_of_child": "feature-to-feature composite links",
    "FeatureRepository.list_subfeature_ids": "feature-to-feature composite links",
    # The one exemption on this repository that is about project data, and the
    # only reason it is safe is that the number never reaches a caller: it
    # decides whether delete_feature refuses, and the refusal carries no count.
    # Scoping it would make a feature referenced only from an unreachable
    # project look deletable, and the delete would then fail at the flush as a
    # 500 instead of the 409 that belongs there. Its sibling
    # segmentation_counts is display data and is deliberately NOT listed here.
    "FeatureRepository.count_segmentations": "referential-integrity guard behind "
    "the delete-conflict check; deletion is global, and the count never leaves "
    "the service",
    "SearchRepository.tag_names": "search-form vocabulary",
    "SearchRepository.active_form_creator_names": "search-form vocabulary",
    "SearchRepository.attribute_signature_rows": "attribute definitions, not rows",
    "SearchRepository.column_values": "generic vocabulary wrapper; every remaining "
    "call site passes Creator, DeviceModel, Feature or FormSchema",
    "SearchRepository.resolve_attribute_definitions": "attribute definitions",
    # Project *resolution*, not row access: each returns the project set that a
    # write check is then judged on, so filtering it by the caller's own scope
    # would delete exactly the projects the check exists to catch and make
    # every floor built on it pass vacuously.
    "TaskRepository.project_ids": "resolves the projects a write is judged on",
    "SubTaskRepository.project_ids": "resolves the projects a write is judged on",
    "SegmentationRepository.project_ids": "resolves the projects a write is judged on",
    "ModelSegmentationRepository.project_ids": "resolves the projects a write is "
    "judged on",
    "FormAnnotationRepository.project_ids": "resolves the projects a write is "
    "judged on",
    "StudyRepository.project_ids": "resolves the projects a write is judged on",
    "ImageInstanceRepository.project_ids": "resolves the projects a write is "
    "judged on",
    "ImageInstanceRepository.project_ids_for_images": "resolves the projects a "
    "batch of enqueue ids is judged on",
    "FormAnnotationRepository.project_ids_of_patient": "resolves the project a "
    "form annotation would be created into; the create floor has no row of its "
    "own to resolve yet",
    "SubTaskRepository.project_ids_of_image": "resolves the project an image "
    "would bring into a task; the *after* half of a link write",
    "SubTaskRepository.resolve_image_instance_id": "PublicID -> id resolution only; "
    "returns an int that is unusable without a subtask to attach it to",
    "SubTaskRepository.next_image_index": "returns an integer, not a row",
    # Deliberately unscoped: SubTaskImageLink is in neither scoping registry,
    # and registering it as single-project would expose the A-side link of a
    # project-spanning task -- the partial view containment exists to prevent.
    # Containment belongs at the subtask, which is scoped -- and both callers
    # now honour it: add_image and remove_image each reject an out-of-scope
    # subtask before they reach this method.
    "SubTaskRepository.get_image_link": "a composite-PK link row that never "
    "reaches a response; see the note above on where containment belongs",
}

# A write with a name the read heuristic would otherwise mistake for a read.
_WRITE_PREFIXES = ("add", "save", "delete", "upsert", "remove", "replace")

# Exact count of read methods the guard must have to check. A discovery
# mechanism that quietly stops finding methods still reports green, so the
# number is pinned rather than merely asserted non-zero. Moving it is a
# deliberate act: it means a read was added, removed or exempted.
_EXPECTED_SCANNED_READS = 37

# Read methods allowed to scope themselves by consuming ``self._scope`` instead
# of calling ``apply_scope``/``scoped_one``. Set equality, like every other
# allow-list here: a method that loses its real scoping and keeps a live-looking
# mention of the scope lands in this set, and adding it becomes a deliberate,
# reviewable act rather than something a green suite hides.
#
# The one entry is the anchor case ``_consumes_the_scope_directly`` documents:
# Project has no route to itself, so this method filters Project.ProjectID
# against the scope by hand. Its *behaviour* is pinned by
# test_instance_signature_empty_scope_sees_no_project_names and
# test_study_signature_scopes_project_names_to_the_caller, so nothing about it
# rests on this structural guard alone.
_SCOPE_ATTRIBUTE_READS = {
    "SearchRepository.visible_project_names",
}

# Every function under server/dtos/ that touches a Session, pinned exactly.
# A DTO converter is a read surface that satisfies both scope guards while
# reading whatever it likes, so the set is frozen rather than merely bounded:
# a new entry means a new unguarded read. These are known, open, and NOT
# blessed as safe -- patient_to_detail_get resolves Registration image ids on
# the raw request session with no scope in the chain.
#
# ``form_annotation_to_get`` was on this list and came off it: it no longer
# resolves an image id itself at all, and reads one only off a relationship a
# scoped repository already loaded. The pin comes down with it, which is what
# "set equality" is for -- a stale entry would read as a still-open hole.
_DTO_SESSION_TOUCHES = {
    "DTOConverter._get_public_id_for_instance_id",
    "DTOConverter._registration_attr_to_public_ids",
    "DTOConverter.patient_to_detail_get",
    "DTOConverter.model_segmentation_to_get",
    "DTOConverter.segmentation_to_get",
}


def _is_read(name: str) -> bool:
    return not name.startswith("_") and not name.startswith(_WRITE_PREFIXES)


def _calls_a_scoping_helper(node: ast.AST) -> bool:
    """True if the body calls ``apply_scope`` or ``scoped_one``."""
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id in {"apply_scope", "scoped_one"}
        for child in ast.walk(node)
    )


def _consumes_the_scope_directly(node: ast.AST) -> bool:
    """True if the body *uses* ``self._scope`` rather than merely naming it.

    ``self._scope`` has to count for something, because a scoped read need not
    go through ``apply_scope``: ``Project`` is the anchor other entities route
    *to* and has no route of its own, so
    ``SearchRepository.visible_project_names`` filters ``Project.ProjectID``
    against the scope directly. Accepting only the two helper names would force
    that method onto the exemption list, where it would read as "deliberately
    unfiltered" -- the opposite of true.

    But a *mention* is not a use. The previous version of this returned True for
    any ``self._scope`` node anywhere in the body, so deleting a method's real
    scoping and leaving ``_ = self._scope`` behind kept the guard green: it
    protected against removing the call, not against neutering it. So the
    reference must now be **consumed** -- read through (``self._scope.is_admin``),
    passed to something, compared, subscripted -- and an inert one is ignored.
    Inert means the node is a bare expression statement, or is the whole
    right-hand side of an assignment: exactly the two shapes a neutering edit
    leaves behind.

    Bound, so this is not over-trusted: a *deeper* dead expression
    (``_ = self._scope.project_ids``) still reads as consumed. Nothing here can
    tell that value from one that reaches the query. What bounds it is
    ``_SCOPE_ATTRIBUTE_READS`` below -- only the methods named there may qualify
    this way at all, and the one method on it is pinned behaviourally in
    ``server/tests/test_routes_search_signature.py``.
    """
    consumed: set[int] = set()
    for parent in ast.walk(node):
        inert = set()
        if isinstance(parent, ast.Expr):
            inert = {id(parent.value)}
        elif isinstance(parent, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            inert = {id(parent.value)} if parent.value is not None else set()
        for child in ast.iter_child_nodes(parent):
            if id(child) not in inert:
                consumed.add(id(child))

    return any(
        isinstance(child, ast.Attribute)
        and child.attr == "_scope"
        and isinstance(child.value, ast.Name)
        and child.value.id == "self"
        and id(child) in consumed
        for child in ast.walk(node)
    )


def _scanned_reads() -> list[tuple[str, str, ast.AST]]:
    """(qualname, filename, body) for every read method the guard must check."""
    assert _REPOSITORIES.is_dir(), (
        f"{_REPOSITORIES} is not a directory -- rglob() would yield nothing "
        "and this guard would pass vacuously"
    )
    found: list[tuple[str, str, ast.AST]] = []
    for path in sorted(_REPOSITORIES.rglob("*.py")):
        if "__pycache__" in path.parts or path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if node.name in _UNSCOPED_REPOSITORIES:
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name == "__init__" or not _is_read(item.name):
                    continue
                qualname = f"{node.name}.{item.name}"
                if qualname in _UNSCOPED_METHODS:
                    continue
                found.append((qualname, path.name, item))
    return found


def _scanned_classes() -> set[str]:
    """Every class name visible to the same file walk ``_scanned_reads`` uses.

    Kept as a literal copy of that walk's file-discovery loop (same
    ``__pycache__``/leading-underscore skip), rather than a refactor shared
    with ``_scanned_reads``, so a future edit to one does not silently drag
    the other out of sync. A repository class defined in a module the skip
    hides -- ``_internal_repository.py``, say -- would never show up here.
    """
    classes: set[str] = set()
    for path in sorted(_REPOSITORIES.rglob("*.py")):
        if "__pycache__" in path.parts or path.name.startswith("_"):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name)
    return classes


def test_the_class_walk_sees_every_repository_class():
    """A repository hidden by the leading-underscore file skip would be invisible.

    ``_all_repository_classes`` (``test_scope_is_constructor_state.py``) finds
    every ``*Repository`` class via ``pkgutil.walk_packages``, which does not
    skip ``_``-prefixed modules. This guard's own file walk does skip them, so
    a repository added in a module like ``_internal_repository.py`` would
    never reach ``_scanned_reads`` and ``_EXPECTED_SCANNED_READS`` would stay
    unchanged -- a silent hole that neither count-based guard above would
    catch, because both only ever see what this same skip already let through.
    """
    from server.tests.test_scope_is_constructor_state import _all_repository_classes

    expected = {cls.__name__ for cls in _all_repository_classes().values()}
    assert _scanned_classes() >= expected


def test_every_read_of_a_scoped_repository_consults_the_scope():
    offenders = [
        f"{filename}::{qualname}"
        for qualname, filename, body in _scanned_reads()
        if not (
            _calls_a_scoping_helper(body) or _consumes_the_scope_directly(body)
        )
    ]
    assert offenders == []


def test_only_the_allow_listed_reads_scope_themselves_by_hand():
    """Everything else must go through ``apply_scope``/``scoped_one``.

    Without this, any read could qualify by touching ``self._scope``, and the
    guard above would accept a method whose real scoping had been deleted as
    long as something scope-shaped survived the edit. Pinned as an exact set so
    a method *joining* it is as visible as a method leaving.
    """
    by_hand = {
        qualname
        for qualname, _, body in _scanned_reads()
        if _consumes_the_scope_directly(body) and not _calls_a_scoping_helper(body)
    }
    assert by_hand == _SCOPE_ATTRIBUTE_READS


def test_the_read_guard_scans_the_expected_number_of_methods():
    """A guard that discovers nothing passes; the count is the proof it looked.

    Pinned rather than merely non-zero: a rename, a moved directory or a
    stricter ``_is_read`` can halve the surface without emptying it, and a
    half-blind guard reports exactly the same green as a whole one.
    """
    scanned = _scanned_reads()
    assert len(scanned) == _EXPECTED_SCANNED_READS, sorted(q for q, _, _ in scanned)


def test_every_exemption_still_names_something_that_exists():
    """A stale allow-list entry silently un-guards a method that was renamed."""
    from server.tests.test_scope_is_constructor_state import _all_repository_classes

    # _all_repository_classes is keyed by module.ClassName so two same-named
    # classes cannot collide; the allow-lists here are written in short form,
    # so re-key on the way in rather than writing dotted paths twice.
    by_name = {cls.__name__: cls for cls in _all_repository_classes().values()}
    for name in _UNSCOPED_REPOSITORIES:
        assert name in by_name, f"{name} no longer exists"
    for entry in _UNSCOPED_METHODS:
        class_name, method = entry.split(".")
        cls = by_name.get(class_name)
        assert cls is not None, f"{entry}: {class_name} no longer exists"
        assert hasattr(cls, method), f"{entry} no longer exists"


def _dto_session_touches() -> set[str]:
    """Every ``Class.function`` under server/dtos/ that can reach a Session."""
    assert _DTOS.is_dir(), (
        f"{_DTOS} is not a directory -- this guard would pass vacuously"
    )
    touches: set[str] = set()
    for path in sorted(_DTOS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))

        def walk(node: ast.AST, prefix: str) -> None:
            """Descend body-by-body so a name is qualified by its real owner.

            ``ast.walk`` flattens the tree, which would report a method both
            unqualified (found from the module) and qualified (found from its
            class) -- two names for one site, and the unqualified one can
            never be pinned honestly.
            """
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.ClassDef):
                    walk(item, f"{prefix}{item.name}.")
                    continue
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                annotated = any(
                    "Session" in ast.unparse(arg.annotation)
                    for arg in (
                        *item.args.posonlyargs,
                        *item.args.args,
                        *item.args.kwonlyargs,
                    )
                    if arg.annotation is not None
                )
                obtains = any(
                    isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Name)
                    and c.func.id == "object_session"
                    for c in ast.walk(item)
                )
                if annotated or obtains:
                    touches.add(f"{prefix}{item.name}")
                walk(item, prefix)

        walk(tree, "")
    return touches


def test_no_dto_reads_the_database_outside_the_pinned_set():
    """server/dtos/ is a read surface no other guard in this suite can see.

    A converter reads through ``object_session`` or a threaded ``Session``,
    so it filters nothing while the route above it resolves a scope and every
    repository below it is guarded. Set equality, not a subset check: a new
    converter that reads is caught, and removing one forces the pin down
    rather than leaving a stale entry behind.
    """
    assert _dto_session_touches() == _DTO_SESSION_TOUCHES


def test_the_dto_pin_names_only_functions_that_exist():
    """A pinned name that was renamed away would silently stop guarding it."""
    from server.dtos.dto_converter import DTOConverter

    for entry in _DTO_SESSION_TOUCHES:
        class_name, function = entry.split(".")
        assert class_name == "DTOConverter", entry
        assert hasattr(DTOConverter, function), f"{entry} no longer exists"
