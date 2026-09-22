"""Admin is decided in AdminService.__init__; there is no router-level gate."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from eyened_orm import Creator
from eyened_orm.authz.roles import ProjectRole

from ..services.admin_service import AdminService, get_admin_service
from .auth import CurrentUser, get_current_user

router = APIRouter()

RoleName = Literal["read_only", "grader", "project_admin"]


class AdminUserResponse(BaseModel):
    """One human account. ``active`` and ``has_credential`` are orthogonal."""

    id: int
    username: str
    is_admin: bool
    active: bool
    has_credential: bool
    employee_identifier: str | None


class MembershipResponse(BaseModel):
    """One membership."""

    project_id: int
    project_name: str
    role: RoleName


class AdminProjectResponse(BaseModel):
    """One project and how many members it has."""

    id: int
    name: str
    member_count: int


class GrantRequest(BaseModel):
    """The role to hold; user and project are in the path."""

    role: RoleName


class MemberGrantResponse(BaseModel):
    """The membership after a grant; ``changed`` is False if the role was already held."""

    project_id: int
    project_name: str
    user_id: int
    role: RoleName
    changed: bool


class GrantPreviewResponse(BaseModel):
    """``to_grant`` roles would be written; ``already_held`` roles are held, at or above ``role``."""

    user_id: int
    role: RoleName
    to_grant: list[MembershipResponse]
    already_held: list[MembershipResponse]


class CreateUserRequest(BaseModel):
    """A human password account; the password must pass the policy."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class SetActiveRequest(BaseModel):
    """``false`` deactivates; ``true`` reactivates."""

    active: bool


class SetPasswordRequest(BaseModel):
    """The new password; it must pass the policy."""

    password: str = Field(min_length=1)


def _user_response(creator: Creator) -> AdminUserResponse:
    return AdminUserResponse(
        id=creator.CreatorID,
        username=creator.CreatorName,
        is_admin=creator.IsAdmin,
        active=not creator.Inactive,
        has_credential=creator.PasswordHash is not None
        or creator.Password is not None,
        employee_identifier=creator.EmployeeIdentifier,
    )


@router.get("/admin/users", response_model=list[AdminUserResponse])
def list_users(
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return every human account, name-ordered, with per-row state."""
    return [_user_response(creator) for creator in service.list_users()]


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


@router.put(
    "/admin/projects/{project_id}/members/{user_id}",
    response_model=MemberGrantResponse,
)
def grant_membership(
    project_id: int,
    user_id: int,
    body: GrantRequest,
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Grant a user a role in a project, or change the one held."""
    result = service.grant_membership(user_id, project_id, ProjectRole[body.role])
    return MemberGrantResponse(
        project_id=result.project_id,
        project_name=result.project_name,
        user_id=result.creator_id,
        role=result.role.name,
        changed=result.changed,
    )


@router.delete("/admin/projects/{project_id}/members/{user_id}", status_code=204)
def revoke_membership(
    project_id: int,
    user_id: int,
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Remove a membership; 204 whether or not one existed."""
    service.revoke_membership(user_id, project_id)


@router.get(
    "/admin/users/{user_id}/grant-preview", response_model=GrantPreviewResponse
)
def preview_task_grant(
    user_id: int,
    task_id: list[int] = Query(min_length=1),
    role: RoleName = Query(),
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Which projects granting ``role`` for these tasks would add, and which are held."""
    plan = service.preview_task_grant(user_id, task_id, ProjectRole[role])
    return GrantPreviewResponse(
        user_id=plan.creator_id,
        role=role,
        to_grant=[
            MembershipResponse(project_id=pid, project_name=name, role=r.name)
            for pid, name, r in plan.to_grant
        ],
        already_held=[
            MembershipResponse(project_id=pid, project_name=name, role=r.name)
            for pid, name, r in plan.already_held
        ],
    )


@router.post("/admin/users", response_model=AdminUserResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a human password account."""
    return _user_response(service.create_user(body.username, body.password))


@router.put("/admin/users/{user_id}/active", response_model=AdminUserResponse)
def set_user_active(
    user_id: int,
    body: SetActiveRequest,
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Deactivate or reactivate a user; repeating the current state changes nothing."""
    return _user_response(service.set_active(user_id, body.active))


@router.put("/admin/users/{user_id}/password", status_code=204)
def set_user_password(
    user_id: int,
    body: SetPasswordRequest,
    service: AdminService = Depends(get_admin_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Replace a user's password."""
    service.set_password(user_id, body.password)
