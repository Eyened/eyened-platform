"""The subtask image-slot shape: a slot exists iff a link exists.

``subtask_with_images_to_get`` is a pure function written duck-typed
(``getattr(subtask, "SubTaskImageLinks", None)``), so the withheld case is
testable with no authorization in place: hand it a link carrying no loaded
``ImageInstance``.
"""
from types import SimpleNamespace

from eyened_orm.task import SubTaskState
from eyened_orm.utils.factories import (
    make_image_in_project,
    make_project,
)
from server.dtos.dto_converter import DTOConverter


def _subtask_with_links(links):
    return SimpleNamespace(
        SubTaskID=1,
        TaskID=2,
        TaskState=SubTaskState.NotStarted,
        CreatorID=None,
        Comments=None,
        SubTaskImageLinks=links,
    )


def test_subtask_with_images_to_get_yields_the_image_at_its_index(session):
    """A resolved link becomes a slot carrying that image."""
    project = make_project(session, "P-slot")
    image = make_image_in_project(session, project, "slot-1")

    result = DTOConverter.subtask_with_images_to_get(
        _subtask_with_links(
            [SimpleNamespace(ImageIndex=0, ImageInstance=image)]
        )
    )

    assert len(result.images) == 1
    assert result.images[0].image_index == 0
    # Compare against a reference conversion rather than a hand-picked field, so
    # the assertion cannot drift from ImageGET's shape.
    assert result.images[0].image == DTOConverter.image_instance_to_get(image)


def test_subtask_with_images_to_get_nulls_an_unresolved_link(session):
    """The gap is the point: a withheld image must leave a slot, not vanish."""
    project = make_project(session, "P-withheld")
    visible = make_image_in_project(session, project, "visible-1")

    result = DTOConverter.subtask_with_images_to_get(
        _subtask_with_links(
            [
                SimpleNamespace(ImageIndex=0, ImageInstance=visible),
                SimpleNamespace(ImageIndex=1, ImageInstance=None),
                SimpleNamespace(ImageIndex=2, ImageInstance=visible),
            ]
        )
    )

    assert [slot.image_index for slot in result.images] == [0, 1, 2]
    assert result.images[1].image is None
    # A null slot carries an index and nothing else: no image id, no patient,
    # no project name.
    assert result.images[1].model_dump() == {"image_index": 1, "image": None}
    assert result.images[0].image is not None and result.images[2].image is not None
