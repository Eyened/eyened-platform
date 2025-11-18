from eyened_orm import Study, StudyTagLink, Tag
from eyened_orm.tag import TagType
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..dtos.dto_converter import DTOConverter
from ..dtos.dtos_aux import ObjectTagPATCH, ObjectTagPOST, TagMeta
from .auth import CurrentUser, get_current_user

router = APIRouter()


@router.post("/studies/{study_id}/tags", response_model=TagMeta)
async def tag_study(
    study_id: int,
    body: ObjectTagPOST,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Attach a Tag to a Study by tag ID (idempotent)."""
    study = db.get(Study, study_id)
    if not study:
        raise HTTPException(404, "Study not found")
    tag = db.get(Tag, body.tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.Study:
        raise HTTPException(400, "Tag type must be Study")

    link = db.get(StudyTagLink, {"TagID": tag.TagID, "StudyID": study_id})
    if not link:
        link = StudyTagLink(
            TagID=tag.TagID,
            StudyID=study_id,
            CreatorID=current_user.id,
            Comment=body.comment,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        link.Tag = tag
    else:
        if body.comment is not None:
            link.Comment = body.comment
            db.commit()
            db.refresh(link)

    return DTOConverter.link_to_tag_metadata(link)


@router.delete("/studies/{study_id}/tags/{tag_id}", status_code=204)
async def untag_study(
    study_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Remove a Tag from a Study (idempotent)."""
    study = db.get(Study, study_id)
    if not study:
        raise HTTPException(404, "Study not found")
    link = db.get(StudyTagLink, {"TagID": tag_id, "StudyID": study_id})
    if link:
        db.delete(link)
        db.commit()
    return Response(status_code=204)


@router.patch("/studies/{study_id}/tags/{tag_id}", response_model=TagMeta)
async def patch_study_tag(
    study_id: int,
    tag_id: int,
    body: ObjectTagPATCH,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TagMeta:
    """Update comment on an existing Study tag link."""
    study = db.get(Study, study_id)
    if not study:
        raise HTTPException(404, "Study not found")
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "Tag not found")
    if tag.TagType != TagType.Study:
        raise HTTPException(400, "Tag type must be Study")

    link = db.get(StudyTagLink, {"TagID": tag_id, "StudyID": study_id})
    if not link:
        raise HTTPException(404, "Link not found")

    if body.comment is not None:
        link.Comment = body.comment
        db.commit()
        db.refresh(link)
    link.Tag = tag
    return DTOConverter.link_to_tag_metadata(link)
