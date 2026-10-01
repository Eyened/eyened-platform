import { api } from "$lib/api/client";
import { apiInvoke } from "$lib/data/api";
import type {
    AdminProjectResponse,
    AdminUserResponse,
    MembershipResponse,
} from "../../types/openapi_types";

export type RoleName = MembershipResponse["role"];

export async function listUsers(): Promise<AdminUserResponse[]> {
    const res = await apiInvoke(() => api.GET("/admin/users"), "list users");
    return res.data ?? [];
}

export async function createUser(
    username: string,
    password: string,
): Promise<AdminUserResponse> {
    const res = await apiInvoke(
        () => api.POST("/admin/users", { body: { username, password } }),
        "create user",
    );
    return res.data as AdminUserResponse;
}

export async function listMemberships(
    userId: number,
): Promise<MembershipResponse[]> {
    const res = await apiInvoke(
        () =>
            api.GET("/admin/users/{user_id}/memberships", {
                params: { path: { user_id: userId } },
            }),
        "list memberships",
    );
    return res.data ?? [];
}

export async function listProjects(): Promise<AdminProjectResponse[]> {
    const res = await apiInvoke(
        () => api.GET("/admin/projects"),
        "list projects",
    );
    return res.data ?? [];
}

export async function grantMembership(
    projectId: number,
    userId: number,
    role: RoleName,
): Promise<void> {
    await apiInvoke(
        () =>
            api.PUT("/admin/projects/{project_id}/members/{user_id}", {
                params: { path: { project_id: projectId, user_id: userId } },
                body: { role },
            }),
        "grant membership",
    );
}

export async function revokeMembership(
    projectId: number,
    userId: number,
): Promise<void> {
    await apiInvoke(
        () =>
            api.DELETE("/admin/projects/{project_id}/members/{user_id}", {
                params: { path: { project_id: projectId, user_id: userId } },
            }),
        "revoke membership",
    );
}

export async function setActive(
    userId: number,
    active: boolean,
): Promise<void> {
    await apiInvoke(
        () =>
            api.PUT("/admin/users/{user_id}/active", {
                params: { path: { user_id: userId } },
                body: { active },
            }),
        "set active",
    );
}

export async function setPassword(
    userId: number,
    password: string,
): Promise<void> {
    await apiInvoke(
        () =>
            api.PUT("/admin/users/{user_id}/password", {
                params: { path: { user_id: userId } },
                body: { password },
            }),
        "set password",
    );
}
