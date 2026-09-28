import { api } from "$lib/api/client";
import { apiInvoke } from "$lib/data/api";
import type {
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
