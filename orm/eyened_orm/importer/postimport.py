from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from sqlalchemy.orm import Session

from eyened_orm.commands.model_processing import (
    CFI_ATTRIBUTE_MODEL_SLUGS,
    CFI_SEGMENTATION_MODEL_SLUGS,
    OCT_SEGMENTATION_MODEL_SLUGS,
)
from eyened_orm.api_client import get_api_client
from eyened_orm.image_instance import ImageInstance, Modality
from eyened_orm.importer.thumbnails import (
    THUMBNAIL_SIZES,
    run_update_thumbnails_for_image_ids,
    thumbnails_folder,
)

SLUG = Literal[
    "thumbnails",
    *CFI_ATTRIBUTE_MODEL_SLUGS,
    *CFI_SEGMENTATION_MODEL_SLUGS,
    *OCT_SEGMENTATION_MODEL_SLUGS,
]

if TYPE_CHECKING:
    from eyened_orm.api_client import APIClient


class ProcessMode(StrEnum):
    SKIP = "skip"
    ENQUEUE = "enqueue"  # API / worker
    LOCAL = "local"  # same functions as RQ, same process


def _local_cfi_attribute(
    session: Session,
    image_ids: list[int],
    model_slug: str,
    *,
    device: str | None,
) -> None:
    from eyened_orm.commands.model_processing import _get_device, run_cfi_attribute_pipeline

    run_cfi_attribute_pipeline(
        session,
        image_ids,
        model_slug,
        device=_get_device(device),
    )


def _local_cfi_amd(
    session: Session,
    image_ids: list[int],
    *,
    device: str | None,
) -> None:
    from eyened_orm.commands.model_processing import _get_device
    from eyened_orm.inference.cfi_amd_segmentation import run_for_image_ids

    run_for_image_ids(session, image_ids, device=_get_device(device))


def _local_layer_segmentation(
    session: Session,
    image_ids: list[int],
    *,
    device: str | None,
) -> None:
    from eyened_orm.commands.model_processing import _get_device
    from eyened_orm.inference.layer_segmentation import run_for_image_ids

    run_for_image_ids(session, image_ids, device=_get_device(device))


class PostImport:
    """Run post-import processing (thumbnails, models) locally or via API workers."""

    def __init__(
        self,
        images: list[ImageInstance],
        *,
        processing: Mapping[SLUG, ProcessMode],
        print_errors: bool = True,
    ) -> None:
        self.images = images
        self.processing = processing
        self.print_errors = print_errors

    @property
    def client(self) -> APIClient:
        return get_api_client()

    def _mode(self, slug: SLUG) -> ProcessMode:
        return self.processing.get(slug, ProcessMode.SKIP)

    def _run_step(
        self,
        label: str,
        mode: ProcessMode,
        image_ids: list[int],
        *,
        session: Session | None,
        enqueue: Callable[[], None],
        local: Callable[[], None],
    ) -> None:
        if mode not in (ProcessMode.ENQUEUE, ProcessMode.LOCAL) or not image_ids:
            return
        where = "enqueue" if mode == ProcessMode.ENQUEUE else "local"
        print(f"Post-import {label}: {len(image_ids)} image(s) ({where})")
        if mode == ProcessMode.ENQUEUE:
            enqueue()
            return
        if session is None:
            raise ValueError(f"Session is required for local {label}")
        local()

    def run(self, session: Session | None = None, device: str | None = None) -> None:
        all_image_ids = [image.ImageInstanceID for image in self.images]
        cfi_image_ids = [
            image.ImageInstanceID
            for image in self.images
            if image.Modality == Modality.ColorFundus
        ]
        oct_image_ids = [
            image.ImageInstanceID
            for image in self.images
            if image.Modality == Modality.OCT
        ]

        self._run_step(
            "thumbnails",
            self._mode("thumbnails"),
            all_image_ids,
            session=session,
            enqueue=lambda: self.client.enqueue_update_thumbnails_for_image_ids(
                all_image_ids,
                print_errors=self.print_errors,
            ),
            local=lambda: run_update_thumbnails_for_image_ids(
                session,
                all_image_ids,
                thumbnails_folder=thumbnails_folder(),
                sizes=THUMBNAIL_SIZES,
                print_errors=self.print_errors,
            ),
        )

        for slug in CFI_ATTRIBUTE_MODEL_SLUGS:
            self._run_step(
                slug,
                self._mode(slug),
                cfi_image_ids,
                session=session,
                enqueue=lambda s=slug: self.client.enqueue_run_cfi_models(
                    image_ids=cfi_image_ids, model=s
                ),
                local=lambda s=slug: _local_cfi_attribute(
                    session, cfi_image_ids, s, device=device
                ),
            )

        self._run_step(
            "cfi-amd",
            self._mode("cfi-amd"),
            cfi_image_ids,
            session=session,
            enqueue=lambda: self.client.enqueue_run_cfi_amd(image_ids=cfi_image_ids),
            local=lambda: _local_cfi_amd(session, cfi_image_ids, device=device),
        )

        self._run_step(
            "layer-segmentation",
            self._mode("layer-segmentation"),
            oct_image_ids,
            session=session,
            enqueue=lambda: self.client.enqueue_run_layer_segmentation(
                image_ids=oct_image_ids
            ),
            local=lambda: _local_layer_segmentation(
                session, oct_image_ids, device=device
            ),
        )
