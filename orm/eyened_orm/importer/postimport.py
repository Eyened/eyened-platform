from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from sqlalchemy.orm import Session

from eyened_orm.api_client import get_api_client
from eyened_orm.image_instance import ImageInstance
from eyened_orm.importer.thumbnails import (
    THUMBNAIL_SIZES,
    run_update_thumbnails_for_image_ids,
    thumbnails_folder,
)
from eyened_orm.inference.registry import MODEL_SLUGS, MODELS

SLUG = Literal["thumbnails", *MODEL_SLUGS]

if TYPE_CHECKING:
    from eyened_orm.api_client import APIClient


class ProcessMode(StrEnum):
    SKIP = "skip"
    ENQUEUE = "enqueue"  # API / worker
    LOCAL = "local"  # same functions as RQ, same process


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
        from eyened_orm.inference.runner import run_model

        all_image_ids = [image.ImageInstanceID for image in self.images]
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

        for slug, spec in MODELS.items():
            ids = [
                image.ImageInstanceID
                for image in self.images
                if image.Modality in spec.modalities
            ]
            self._run_step(
                slug,
                self._mode(slug),
                ids,
                session=session,
                enqueue=lambda s=slug, ids=ids: self.client.enqueue_run_model(
                    ids, models=[s]
                ),
                local=lambda s=slug, ids=ids: run_model(session, s, ids, device=device),
            )
