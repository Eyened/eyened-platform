"""
Pydantic DTOs for EyeNed Platform
Auto-generated from TypeScript datamodel mappings

This file contains DTOs that represent:
1. Database field representations (with string field names as they appear in DB)
2. Frontend object representations (with property names as used in TypeScript)
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, get_origin

from pydantic import BaseModel, create_model
from eyened_orm.Tag import TagType

# Type aliases matching TypeScript types
AnnotationTypeInterpretation = Literal[
    "", "R/G mask", "Binary mask", "Label numbers", "Probability", "Layer bits"
]
AnatomicRegion = str  # Based on database field
VesselType = Literal["Artery", "Vein", "Vessel"]

class ObjectTagPOST(BaseModel):
    tag_id: int

# Utility DTOs
class Position2D(BaseModel):
    x: float
    y: float


class ROI(BaseModel):
    cx: float
    cy: float
    radius: float
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    w: float
    h: float


class Keypoints(BaseModel):
    fovea_xy: tuple[float, float]
    disc_edge_xy: tuple[float, float]
    prep_fovea_xy: tuple[float, float]
    prep_disc_edge_xy: tuple[float, float]


# === CREATOR ===
class CreatorBase(BaseModel):
    """Creator frontend object"""

    name: str
    msn: Optional[str] = None
    is_human: bool
    description: Optional[str] = None
    version: Optional[str] = None
    role: Optional[Any] = None


class CreatorPUT(CreatorBase):
    pass


class CreatorGET(CreatorBase):
    id: int
    date_inserted: datetime


class CreatorMetadata(BaseModel):
    id: int
    name: str





# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# ========================= TAGS =========================
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class TagBase(BaseModel):
    name: str
    tag_type: TagType
    description: str


class TagPUT(TagBase):
    pass
    


class TagPATCH(TagPUT):
    """Partial update for Tag (same as PUT for now)."""
    pass


class TagGET(TagBase):
    id: int
    creator: CreatorMetadata
    date_inserted: datetime


class TagMetadata(BaseModel):
    id: int
    name: str
    tagger: CreatorMetadata
    date: datetime