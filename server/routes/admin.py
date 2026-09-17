"""Admin is decided in AdminService.__init__; there is no router-level gate."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..services.admin_service import AdminService, get_admin_service
from .auth import CurrentUser, get_current_user

router = APIRouter()


class AdminUserResponse(BaseModel):
    """One human account. ``active`` and ``has_credential`` are orthogonal."""

    id: int
    username: str
    is_admin: bool
    active: bool
    has_credential: bool
    employee_identifier: str | None


class MembershipResponse(BaseModel):
    """One membership. ``role`` is the enum's name, not its int."""

    project_id: int
    project_name: str
    role: Literal["read_only", "grader", "project_admin"]


class AdminProjectResponse(BaseModel):
    """One project and how many members it has."""

    id: int
    name: str
    member_count: int


@router.get("/admin/users", response_model=list[AdminUserResponse])
def list_users(
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return every human account, name-ordered, with per-row state."""
    return [
        AdminUserResponse(
            id=creator.CreatorID,
            username=creator.CreatorName,
            is_admin=creator.IsAdmin,
            active=not creator.Inactive,
            has_credential=creator.PasswordHash is not None
            or creator.Password is not None,
            employee_identifier=creator.EmployeeIdentifier,
        )
        for creator in service.list_users()
    ]


@router.get(
    "/admin/users/{user_id}/memberships", response_model=list[MembershipResponse]
)
def list_user_memberships(
    user_id: int,
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return one user's project memberships, ordered by project name."""
    return [
        MembershipResponse(project_id=project_id, project_name=name, role=role.name)
        for project_id, name, role in service.memberships_of_user(user_id)
    ]


@router.get("/admin/projects", response_model=list[AdminProjectResponse])
def list_projects(
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return every project, name-ordered, with its member count."""
    return [
        AdminProjectResponse(
            id=project.ProjectID, name=project.ProjectName, member_count=count
        )
        for project, count in service.list_projects()
    ]
