import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { json, stubFetch } from "../../../../../vitest-fetch";

vi.mock("$app/paths", () => ({ resolve: (route: string) => route }));
vi.mock("$app/state", () => ({ page: { params: { id: "3" } } }));

const { default: UserPage } = await import("./+page.svelte");

afterEach(() => vi.unstubAllGlobals());

const alice = {
    id: 3,
    username: "alice",
    is_admin: false,
    active: true,
    has_credential: true,
    employee_identifier: null,
};

const projects = [
    { id: 1, name: "Alpha", member_count: 1 },
    { id: 2, name: "Beta", member_count: 0 },
];

describe("user page", () => {
    it("grants only projects the user does not hold", async () => {
        const grant = vi.fn(() =>
            json({
                project_id: 2,
                project_name: "Beta",
                user_id: 3,
                role: "read_only",
                changed: true,
            }),
        );
        stubFetch({
            "GET /api/admin/users": () => json([alice]),
            "GET /api/admin/users/3/memberships": () =>
                json([
                    { project_id: 1, project_name: "Alpha", role: "grader" },
                ]),
            "GET /api/admin/projects": () => json(projects),
            "PUT /api/admin/projects/2/members/3": grant,
        });
        render(UserPage);

        const select = await screen.findByLabelText("Project");
        expect(within(select).queryByText("Alpha")).toBeNull();
        await fireEvent.change(select, { target: { value: "2" } });
        await fireEvent.click(screen.getByRole("button", { name: "Grant" }));

        await vi.waitFor(() =>
            expect(grant).toHaveBeenCalledWith({ role: "read_only" }),
        );
    });

    it("says so when the user does not exist", async () => {
        stubFetch({
            "GET /api/admin/users": () => json([]),
            "GET /api/admin/users/3/memberships": () =>
                json({ detail: "User 3 not found" }, 404),
            "GET /api/admin/projects": () => json(projects),
        });
        render(UserPage);

        expect(await screen.findByText("User not found")).toBeInTheDocument();
    });

    it("revokes only after confirmation", async () => {
        const revoke = vi.fn(() => json(null, 204));
        stubFetch({
            "GET /api/admin/users": () => json([alice]),
            "GET /api/admin/users/3/memberships": () =>
                json([
                    { project_id: 1, project_name: "Alpha", role: "grader" },
                ]),
            "GET /api/admin/projects": () => json(projects),
            "DELETE /api/admin/projects/1/members/3": revoke,
        });
        render(UserPage);

        await fireEvent.click(
            await screen.findByRole("button", { name: "Revoke" }),
        );
        await fireEvent.click(
            await screen.findByRole("button", { name: "Cancel" }),
        );
        expect(revoke).not.toHaveBeenCalled();

        await fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
        await fireEvent.click(
            await screen.findByRole("button", { name: "Confirm" }),
        );
        await vi.waitFor(() => expect(revoke).toHaveBeenCalledTimes(1));
    });

    it.each([
        { active: true, button: "Deactivate", sent: false },
        { active: false, button: "Reactivate", sent: true },
    ])("$button sends active: $sent", async ({ active, button, sent }) => {
        const setActive = vi.fn(() => json({ ...alice, active: sent }));
        stubFetch({
            "GET /api/admin/users": () => json([{ ...alice, active }]),
            "GET /api/admin/users/3/memberships": () => json([]),
            "GET /api/admin/projects": () => json(projects),
            "PUT /api/admin/users/3/active": setActive,
        });
        render(UserPage);

        await fireEvent.click(
            await screen.findByRole("button", { name: button }),
        );
        // Reactivate is not destructive, so only Deactivate asks for confirmation.
        if (active) {
            await fireEvent.click(
                await screen.findByRole("button", { name: "Confirm" }),
            );
        }
        await vi.waitFor(() =>
            expect(setActive).toHaveBeenCalledWith({ active: sent }),
        );
    });
});
