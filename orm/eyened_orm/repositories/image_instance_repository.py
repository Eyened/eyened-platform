from __future__ import annotations

from sqlalchemy.orm import Session, selectinload, with_loader_criteria

from eyened_orm import (
    DeviceInstance,
    FormAnnotation,
    ImageInstance,
    ImageInstanceTagLink,
    ImageStorage,
    ModelSegmentation,
    Patient,
    Segmentation,
    Series,
    Study,
)
from eyened_orm.tag import FormAnnotationTagLink, SegmentationTagLink
from eyened_orm.authz.scope import AccessScope
from eyened_orm.authz.scoping import (
    image_project_pairs,
    projects_of,
    scope_criteria,
)

from ._scoped import scoped_one

_STORAGE_LOADER = selectinload(ImageInstance.ImageStorages).selectinload(
    ImageStorage.StorageBackend
)


class ImageInstanceRepository:
    """Data access for ImageInstance reads and its Tag links."""

    def __init__(self, session: Session, *, scope: AccessScope) -> None:
        self._session = session
        self._scope = scope

    def _full_graph_options(
        self,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> list:
        """Build the conditional selectinload chain the two GET readers share.

        A method rather than a module helper because the ``FormAnnotations``
        branch needs the caller's scope, and a scope is this repository's
        constructor state -- never a per-call argument.

        Why that branch needs it at all: ``scoped_one`` filters the statement's
        *root*, and a ``selectinload`` runs its own SELECT that the root's
        WHERE never reaches. Every other load here stays on the image's own
        ``Patient`` chain, so the root filter already governs it;
        ``FormAnnotation`` is anchored to its ``PatientID`` instead, which can
        differ from the image's, and that collection therefore carries the
        caller's predicate itself.
        """
        opts = [
            selectinload(ImageInstance.Series)
            .selectinload(Series.Study)
            .selectinload(Study.Patient)
            .selectinload(Patient.Project),
            selectinload(ImageInstance.DeviceInstance).selectinload(
                DeviceInstance.DeviceModel
            ),
            selectinload(ImageInstance.Scan),
            _STORAGE_LOADER,
            selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
                ImageInstanceTagLink.Tag
            ),
            selectinload(ImageInstance.ImageInstanceTagLinks).selectinload(
                ImageInstanceTagLink.Creator
            ),
        ]
        if with_segmentations:
            opts += [
                selectinload(ImageInstance.Segmentations).selectinload(
                    Segmentation.Feature
                ),
                selectinload(ImageInstance.Segmentations).selectinload(
                    Segmentation.Creator
                ),
                selectinload(ImageInstance.Segmentations)
                .selectinload(Segmentation.SegmentationTagLinks)
                .selectinload(SegmentationTagLink.Tag),
                selectinload(ImageInstance.Segmentations)
                .selectinload(Segmentation.SegmentationTagLinks)
                .selectinload(SegmentationTagLink.Creator),
            ]
        if with_form_annotations:
            opts += [
                selectinload(ImageInstance.FormAnnotations)
                .selectinload(FormAnnotation.FormAnnotationTagLinks)
                .selectinload(FormAnnotationTagLink.Tag),
                selectinload(ImageInstance.FormAnnotations)
                .selectinload(FormAnnotation.FormAnnotationTagLinks)
                .selectinload(FormAnnotationTagLink.Creator),
                # The annotation DTO names an image only off a *loaded*
                # relationship -- it resolves none itself -- so without this
                # every annotation nested in this response comes back with
                # ``image_id: null``. No scope criteria on this one, and it
                # needs none: this collection is the root image's own
                # ``FormAnnotations``, so each row's ``ImageInstanceID`` is the
                # root's by construction and the root read already scoped it.
                #
                # ``lazyload("*")`` is what keeps it cheap, and it is not
                # optional. The nested object *is* the root image, already
                # fully populated by this same option chain, but loading it
                # again re-triggers ``ImageInstance``'s own ``lazy="selectin"``
                # relationships -- Series/Study/Patient/Project, ImageStorage/
                # StorageBackend, device, tags. Measured on
                # ``get_instance(..., with_form_annotations=True)`` with three
                # nested annotations: 14 statements with this leg absent (and
                # ``image_id: null``), 26 with the leg alone, 15 with the leg
                # and this suppression. Suppressing the re-cascade changes
                # nothing the DTO reads.
                selectinload(ImageInstance.FormAnnotations)
                .selectinload(FormAnnotation.ImageInstance)
                .lazyload("*"),
            ]
            criteria = scope_criteria(FormAnnotation, self._scope)
            if criteria is not None:
                # None is an admin (or an unfiltered entity), where adding a
                # tautology would read as a filter that is in force. The predicate
                # is the same one ``apply_scope`` puts on a FormAnnotation read, so
                # this collection and ``GET /form-annotations/{id}`` cannot give
                # two answers for one row.
                opts.append(with_loader_criteria(FormAnnotation, criteria))
        if with_model_segmentations:
            opts += [
                selectinload(ImageInstance.ModelSegmentations).selectinload(
                    ModelSegmentation.Model
                ),
            ]
        return opts

    def project_ids(self, image_instance_id: int) -> set[int]:
        """The project this image sits in, for a write check to be judged on.

        The repository owns the Session, so the authz resolution runs here
        rather than a service reaching through for a Session it must not hold.
        Uses ``projects_of``, the one definition the reads and the CLI share.

        Deliberately unscoped: the returned set is the *input* to
        ``AccessScope.require``, so filtering it by the caller's scope would
        remove exactly the projects the check exists to catch and make every
        floor pass.
        """
        return projects_of(self._session, ImageInstance, image_instance_id)

    def project_ids_for_images(
        self, image_instance_ids: list[int]
    ) -> dict[int, int]:
        """Return {image_instance_id: project_id} for the given ids, in one query.

        Ids that resolve to no image are simply absent, so the caller can tell
        "unknown" from "known" and answer both the same way.

        Unscoped by design: this is project *resolution*, and the returned
        projects are the input to the caller's check. Filtering it by the scope
        would make every check trivially pass. Listed in the read-coverage
        guard's exemptions.

        Resolves through ``image_project_pairs`` rather than its own join, so
        this gate and the read filters share the one declaration of an image's
        route to its project.
        """
        rows = self._session.execute(image_project_pairs(image_instance_ids)).all()
        return {int(image_id): int(project_id) for image_id, project_id in rows}

    def get_full_graph_by_id(
        self,
        instance_id: int,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance | None:
        """Return the instance by int id with the conditional graph, or None."""
        opts = self._full_graph_options(
            with_segmentations, with_form_annotations, with_model_segmentations
        )
        return scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.ImageInstanceID == instance_id,
            options=tuple(opts),
        )

    def get_full_graph_by_public_id(
        self,
        image_id: str,
        *,
        with_segmentations: bool,
        with_form_annotations: bool,
        with_model_segmentations: bool,
    ) -> ImageInstance | None:
        """Return the instance by PublicID (numeric-PK fallback), or None."""
        opts = self._full_graph_options(
            with_segmentations, with_form_annotations, with_model_segmentations
        )
        item = scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.PublicID == image_id,
            options=tuple(opts),
        )
        if item is None and image_id.isdigit():
            # The numeric-PK fallback is a second lookup, so it needs the filter
            # too -- an unscoped fallback would be a read bypass reachable by
            # simply passing the integer id as a string.
            item = scoped_one(
                self._session,
                ImageInstance,
                self._scope,
                ImageInstance.ImageInstanceID == int(image_id),
                options=tuple(opts),
            )
        return item

    def get_with_storage_by_public_id(
        self, public_id: str
    ) -> ImageInstance | None:
        """Return the instance by PublicID with storage loaded (PK fallback), or None.

        Mirrors the legacy ``_get_image_instance_by_public_id`` resolver: try the
        PublicID; on no match fall back to the raw id (numeric-PK fallback).

        ``scoped_one`` takes the first row rather than raising on a second, as
        the previous ``.one()`` did. Safe only because ``ImageInstance.PublicID``
        is UNIQUE NOT NULL -- there is no second row to pick between. Drop that
        constraint and this silently returns an arbitrary one, unordered.
        """
        item = scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.PublicID == public_id,
            options=(_STORAGE_LOADER,),
        )
        if item is None and public_id.isdigit():
            item = scoped_one(
                self._session,
                ImageInstance,
                self._scope,
                ImageInstance.ImageInstanceID == int(public_id),
                options=(_STORAGE_LOADER,),
            )
        return item

    def get_tag_link(
        self, tag_id: int, image_instance_id: int
    ) -> ImageInstanceTagLink | None:
        """Return the link for (tag_id, image_instance_id), or None if absent/out of scope."""
        return scoped_one(
            self._session,
            ImageInstanceTagLink,
            self._scope,
            ImageInstanceTagLink.TagID == tag_id,
            ImageInstanceTagLink.ImageInstanceID == image_instance_id,
        )

    def save_link(self, link: ImageInstanceTagLink) -> None:
        """Persist in-place mutations to ``link`` (e.g. ``Comment``) within the
        request transaction.

        ``link`` names what is being saved; the flush covers the whole unit of
        work, deliberately not just this row.
        """
        self._session.flush()

    def get_by_public_id(self, public_id: str) -> ImageInstance | None:
        """Return the instance with this PublicID (no eager loads), or None.

        Plain PublicID resolver used to map an external image id to its row —
        the faithful equivalent of the legacy ``_resolve_image_instance_id``
        helper (no PK/digit fallback, unlike ``get_full_graph_by_public_id``).
        """
        return scoped_one(
            self._session,
            ImageInstance,
            self._scope,
            ImageInstance.PublicID == public_id,
        )

    def add_link(
        self,
        *,
        tag_id: int,
        image_instance_id: int,
        creator_id: int,
        comment: str | None,
    ) -> ImageInstanceTagLink:
        """Create an ImageInstanceTagLink and flush so its row (and PK) is written."""
        link = ImageInstanceTagLink(
            TagID=tag_id,
            ImageInstanceID=image_instance_id,
            CreatorID=creator_id,
            Comment=comment,
        )
        self._session.add(link)
        self._session.flush()
        return link

    def delete_link(self, link: ImageInstanceTagLink) -> None:
        """Delete an ImageInstanceTagLink and flush within the request transaction."""
        self._session.delete(link)
        self._session.flush()
