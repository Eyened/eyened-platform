from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from sqlalchemy.orm import Session

from eyened_orm.commands.model_processing import (
    CFI_ATTRIBUTE_MODEL_SLUGS,
    CFI_SEGMENTATION_MODEL_SLUGS,
    OCT_SEGMENTATION_MODEL_SLUGS,
    run_cfi_attribute_pipeline,
)
from eyened_orm.inference.cfi_amd_segmentation import (
    run_for_image_ids as run_cfi_amd_for_image_ids,
)
from eyened_orm.inference.layer_segmentation import (
    run_for_image_ids as run_layer_segmentation_for_image_ids,
)
from eyened_orm.api_client import get_api_client
from eyened_orm.commands.model_processing import _get_device
from eyened_orm.image_instance import ImageInstance, Modality
from eyened_orm.importer.thumbnails import run_update_thumbnails_for_image_ids


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


class PostProcess:
    """Run thumbnail and CFI post-import steps (enqueue on worker or in-process)."""

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

        if self.processing.get("thumbnails") == ProcessMode.ENQUEUE:
            self.client.enqueue_update_thumbnails_for_image_ids(
                all_image_ids,
                print_errors=self.print_errors,
            )
        elif self.processing.get("thumbnails") == ProcessMode.LOCAL:
            if session is None:
                raise ValueError("Session is required for local thumbnail processing")
            run_update_thumbnails_for_image_ids(
                session,
                all_image_ids,
                print_errors=self.print_errors,
            )

        if cfi_image_ids:
            for slug in CFI_ATTRIBUTE_MODEL_SLUGS:
                if slug not in self.processing:
                    continue
                mode = self.processing[slug]

                if mode == ProcessMode.ENQUEUE:
                    self.client.enqueue_run_cfi_models(
                        image_ids=cfi_image_ids, model=slug
                    )
                elif mode == ProcessMode.LOCAL:
                    if session is None:
                        raise ValueError("Session is required for local CFI processing")
                    run_cfi_attribute_pipeline(
                        session,
                        cfi_image_ids,
                        slug,
                        device=_get_device(device),
                    )
            if "cfi-amd" in self.processing:
                mode = self.processing["cfi-amd"]
                if mode == ProcessMode.ENQUEUE:
                    self.client.enqueue_run_cfi_amd(image_ids=cfi_image_ids)
                elif mode == ProcessMode.LOCAL:
                    if session is None:
                        raise ValueError(
                            "Session is required for local CFI segmentation processing"
                        )
                    run_cfi_amd_for_image_ids(
                        session,
                        cfi_image_ids,
                        device=_get_device(device),
                    )

        if oct_image_ids and "layer-segmentation" in self.processing:
            mode = self.processing["layer-segmentation"]
            if mode == ProcessMode.ENQUEUE:
                self.client.enqueue_run_layer_segmentation(image_ids=oct_image_ids)
            elif mode == ProcessMode.LOCAL:
                if session is None:
                    raise ValueError(
                        "Session is required for local OCT segmentation processing"
                    )
                run_layer_segmentation_for_image_ids(
                    session,
                    oct_image_ids,
                    device=_get_device(device),
                )
