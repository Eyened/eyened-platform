"""Composable model builders and a fixed dataset for search/annotation tests.

Lives beside ``sqlite_testdb`` so both ``orm`` and ``server`` test suites can
import it. Builders ``flush()`` (never ``commit()``) so callers control the
transaction; only ``seed_search_dataset`` commits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    # Type-checking only, so the quoted annotations on admin_scope/scope_for
    # actually resolve -- an annotation that cannot resolve is not an
    # annotation. The runtime imports stay function-local (see those two
    # functions) to keep this module's import cheap.
    from eyened_orm.authz.roles import ProjectRole
    from eyened_orm.authz.scope import AccessScope

from eyened_orm import (
    Creator,
    DeviceInstance,
    DeviceModel,
    Feature,
    FormAnnotation,
    FormAnnotationTagLink,
    FormSchema,
    ImageInstance,
    ImageInstanceTagLink,
    ImageStorage,
    Patient,
    Project,
    Segmentation,
    SegmentationTagLink,
    Series,
    StorageBackend,
    Study,
    StudyTagLink,
    Tag,
)
from eyened_orm.attributes import (
    AttributeDataType,
    AttributeDefinition,
    AttributesModel,
    AttributesModelOutput,
    AttributeValue,
)
from eyened_orm.patient import SexEnum
from eyened_orm.project import ExternalEnum
from eyened_orm.segmentation import DataRepresentation, Datatype
from eyened_orm.tag import TagType


def make_storage_backend(session: Session, key: str = "test-backend") -> StorageBackend:
    b = StorageBackend(Key=key, Kind="local")
    session.add(b)
    session.flush()
    return b


def make_creator(session: Session, name: str, is_human: bool = True) -> Creator:
    c = Creator(CreatorName=name, IsHuman=is_human)
    session.add(c)
    session.flush()
    return c


def make_project(session: Session, name: str) -> Project:
    p = Project(ProjectName=name, External=ExternalEnum.N)
    session.add(p)
    session.flush()
    return p


def make_patient(session, project, identifier, birth_date=None, sex=None) -> Patient:
    p = Patient(
        PatientIdentifier=identifier,
        ProjectID=project.ProjectID,
        BirthDate=birth_date,
        Sex=sex,
    )
    session.add(p)
    session.flush()
    return p


def make_study(session, patient, study_date, description=None, study_round=None) -> Study:
    s = Study(
        PatientID=patient.PatientID,
        StudyDate=study_date,
        StudyDescription=description,
        StudyRound=study_round,
    )
    session.add(s)
    session.flush()
    return s


def make_series(session, study) -> Series:
    s = Series(StudyID=study.StudyID)
    session.add(s)
    session.flush()
    return s


def make_device(session, key: str) -> DeviceInstance:
    model = DeviceModel(Manufacturer=f"Mf-{key}", ManufacturerModelName=f"M-{key}")
    session.add(model)
    session.flush()
    d = DeviceInstance(DeviceModelID=model.DeviceModelID, Description=f"d-{key}")
    session.add(d)
    session.flush()
    return d


def make_image(
    session,
    series,
    device,
    backend,
    public_id: str,
    *,
    inactive: bool = False,
    date_inserted: datetime | None = None,
    **cols,
) -> ImageInstance:
    """Create an ImageInstance plus the primary ImageStorage the DTO layer requires.

    ``DTOConverter.image_instance_to_get`` raises without a primary storage, so
    the storage row is part of the instance's minimum viable shape, not an extra.
    ``DatasetIdentifier`` is deprecated but still NOT NULL, hence set here.
    """
    img = ImageInstance(
        PublicID=public_id,
        SeriesID=series.SeriesID,
        DeviceInstanceID=device.DeviceInstanceID,
        DatasetIdentifier=f"ds-{public_id}",
        Rows_y=4,
        Columns_x=4,
        Inactive=inactive,
        DateInserted=date_inserted or datetime(2024, 1, 1),
        **cols,
    )
    session.add(img)
    session.flush()
    session.add(
        ImageStorage(
            ImageInstanceID=img.ImageInstanceID,
            StorageBackendID=backend.StorageBackendID,
            ObjectKey=f"obj-{public_id}",
            Format="png",
            IsPrimary=True,
        )
    )
    session.flush()
    return img


def make_feature(session, name: str) -> Feature:
    f = Feature(FeatureName=name)
    session.add(f)
    session.flush()
    return f


def make_segmentation(session, image, feature, creator, *, inactive=False) -> Segmentation:
    seg = Segmentation(
        ImageInstanceID=image.ImageInstanceID,
        FeatureID=feature.FeatureID,
        CreatorID=creator.CreatorID,
        DataType=Datatype.R8UI,
        DataRepresentation=DataRepresentation.Binary,
        Depth=1,
        Height=4,
        Width=4,
        Inactive=inactive,
        DateInserted=datetime(2024, 1, 1),
    )
    session.add(seg)
    session.flush()
    return seg


def make_form_schema(session, name: str) -> FormSchema:
    s = FormSchema(SchemaName=name)
    session.add(s)
    session.flush()
    return s


def make_form_annotation(
    session, schema, patient, creator, *, study=None, image=None, inactive=False
) -> FormAnnotation:
    fa = FormAnnotation(
        FormSchemaID=schema.FormSchemaID,
        PatientID=patient.PatientID,
        CreatorID=creator.CreatorID,
        StudyID=study.StudyID if study is not None else None,
        ImageInstanceID=image.ImageInstanceID if image is not None else None,
        Inactive=inactive,
    )
    session.add(fa)
    session.flush()
    return fa


def make_tag(session, name: str, tag_type: TagType, creator) -> Tag:
    t = Tag(
        TagName=name,
        TagType=tag_type,
        TagDescription=f"desc-{name}",
        CreatorID=creator.CreatorID,
    )
    session.add(t)
    session.flush()
    return t


def make_attribute(session, name: str, dtype: AttributeDataType) -> AttributeDefinition:
    a = AttributeDefinition(AttributeName=name, AttributeDataType=dtype)
    session.add(a)
    session.flush()
    return a


def make_attributes_model(session, name: str, outputs=(), version: str = "1") -> AttributesModel:
    """Create an attributes Model. ``Version`` is NOT NULL on the joined-table parent."""
    m = AttributesModel(ModelName=name, Version=version)
    session.add(m)
    session.flush()
    for attr in outputs:
        session.add(AttributesModelOutput(ModelID=m.ModelID, AttributeID=attr.AttributeID))
    session.flush()
    return m


def make_attribute_value(session, attr, *, image=None, model=None, value=None) -> AttributeValue:
    kwargs = {"AttributeID": attr.AttributeID}
    if image is not None:
        kwargs["ImageInstanceID"] = image.ImageInstanceID
    if model is not None:
        kwargs["ModelID"] = model.ModelID
    if attr.AttributeDataType == AttributeDataType.Int:
        kwargs["ValueInt"] = value
    elif attr.AttributeDataType == AttributeDataType.Float:
        kwargs["ValueFloat"] = value
    else:
        kwargs["ValueText"] = value
    av = AttributeValue(**kwargs)
    session.add(av)
    session.flush()
    return av


@dataclass
class SearchDataset:
    """Handles into the fixed dataset seeded by ``seed_search_dataset``."""

    images: dict[str, ImageInstance] = field(default_factory=dict)
    studies: dict[str, Study] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)


def seed_search_dataset(session: Session) -> SearchDataset:
    """Seed a fixed 2-project graph that lights up every exists_* branch.

    img-a1  project Alpha: segmentation (feat-x / seg-creator / seg-tag),
            image-level form annotation (schema-x / form-creator / form-tag),
            image tag, attribute Quality=5 produced by model M1.
    img-a2  project Alpha: plain, no annotations.
    img-b1  project Beta: plain; its study carries a study-tag and a
            study-level form annotation.
    img-inactive  project Alpha: Inactive=True, must never be returned.
    """
    backend = make_storage_backend(session)
    seg_creator = make_creator(session, "seg-creator")
    form_creator = make_creator(session, "form-creator")

    alpha = make_project(session, "Alpha")
    beta = make_project(session, "Beta")

    pat_a = make_patient(session, alpha, "PAT-A", date(1980, 1, 1), SexEnum.F)
    pat_b = make_patient(session, beta, "PAT-B", date(1990, 2, 2), SexEnum.M)

    study_a = make_study(session, pat_a, date(2024, 1, 1), "study-a", 1)
    study_b = make_study(session, pat_b, date(2024, 6, 1), "study-b", 2)

    ser_a = make_series(session, study_a)
    ser_b = make_series(session, study_b)
    dev = make_device(session, "d1")

    a1 = make_image(session, ser_a, dev, backend, "img-a1", date_inserted=datetime(2024, 1, 1))
    a2 = make_image(session, ser_a, dev, backend, "img-a2", date_inserted=datetime(2024, 1, 2))
    b1 = make_image(session, ser_b, dev, backend, "img-b1", date_inserted=datetime(2024, 6, 1))
    inactive = make_image(
        session, ser_a, dev, backend, "img-inactive",
        inactive=True, date_inserted=datetime(2024, 1, 3),
    )

    feat_x = make_feature(session, "feat-x")
    seg = make_segmentation(session, a1, feat_x, seg_creator)

    schema_x = make_form_schema(session, "schema-x")
    fa_img = make_form_annotation(session, schema_x, pat_a, form_creator, image=a1)
    make_form_annotation(session, schema_x, pat_b, form_creator, study=study_b)

    seg_tag = make_tag(session, "seg-tag", TagType.Segmentation, seg_creator)
    form_tag = make_tag(session, "form-tag", TagType.FormAnnotation, form_creator)
    img_tag = make_tag(session, "img-tag", TagType.ImageInstance, seg_creator)
    study_tag = make_tag(session, "study-tag", TagType.Study, seg_creator)

    session.add(SegmentationTagLink(
        SegmentationID=seg.SegmentationID, TagID=seg_tag.TagID, CreatorID=seg_creator.CreatorID))
    session.add(FormAnnotationTagLink(
        FormAnnotationID=fa_img.FormAnnotationID, TagID=form_tag.TagID, CreatorID=form_creator.CreatorID))
    session.add(ImageInstanceTagLink(
        ImageInstanceID=a1.ImageInstanceID, TagID=img_tag.TagID, CreatorID=seg_creator.CreatorID))
    session.add(StudyTagLink(
        StudyID=study_b.StudyID, TagID=study_tag.TagID, CreatorID=seg_creator.CreatorID))

    quality = make_attribute(session, "Quality", AttributeDataType.Int)
    m1 = make_attributes_model(session, "M1", outputs=[quality])
    make_attribute_value(session, quality, image=a1, model=m1, value=5)

    session.commit()
    return SearchDataset(
        images={"a1": a1, "a2": a2, "b1": b1, "inactive": inactive},
        studies={"a": study_a, "b": study_b},
        projects={"alpha": alpha, "beta": beta},
    )


def admin_scope(actor_id: int = 1, username: str = "tester") -> "AccessScope":
    """An unrestricted scope, for tests whose subject is not authorization."""
    from eyened_orm.authz.scope import AccessScope

    return AccessScope(
        actor_id=actor_id, username=username, is_admin=True, roles={}
    )


def scope_for(
    *project_ids: int,
    role: "ProjectRole | None" = None,
    actor_id: int = 1,
    username: str = "tester",
) -> "AccessScope":
    """A non-admin scope holding ``role`` in each of ``project_ids``."""
    from eyened_orm.authz.roles import ProjectRole
    from eyened_orm.authz.scope import AccessScope

    return AccessScope(
        actor_id=actor_id,
        username=username,
        is_admin=False,
        roles={p: role or ProjectRole.grader for p in project_ids},
    )
