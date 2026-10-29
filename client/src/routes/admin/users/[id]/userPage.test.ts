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

const alpha = { project_id: 1, project_name: "Alpha", role: "grader" };

function stubUser(
    routes: Record<string, (body: unknown) => Response> = {},
    memberships: unknown[] = [alpha],
    user = alice,
) {
    return stubFetch({
        "GET /api/admin/users": () => json([user]),
        "GET /api/admin/users/3/memberships": () => json(memberships),
        "GET /api/admin/projects": () => json(projects),
        ...routes,
    });
}

describe("user page", () => {
    it("adds the user only to projects they are not in", async () => {
        const grant = vi.fn(() =>
            json({
                project_id: 2,
                project_name: "Beta",
                user_id: 3,
                role: "read_only",
                changed: true,
            }),
        );
        stubUser({ "PUT /api/admin/projects/2/members/3": grant });
        render(UserPage);

        await fireEvent.click(
            await screen.findByRole("button", { name: "Add to project" }),
        );
        const dialog = await screen.findByRole("dialog");
        const select = within(dialog).getByLabelText("Project");
        expect(within(select).queryByText("Alpha")).toBeNull();
        await fireEvent.change(select, { target: { value: "2" } });
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Add" }),
        );

        await vi.waitFor(() =>
            expect(grant).toHaveBeenCalledWith({ role: "read_only" }),
        );
    });

    it("disables Add to project when the user is in every project", async () => {
        stubUser({}, [
            alpha,
            { project_id: 2, project_name: "Beta", role: "read_only" },
        ]);
        render(UserPage);

        expect(
            await screen.findByRole("button", { name: "Add to project" }),
        ).toHaveAttribute("aria-disabled", "true");
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

    it("removes a membership only from a danger modal named for the action", async () => {
        const revoke = vi.fn(() => json(null, 204));
        stubUser({ "DELETE /api/admin/projects/1/members/3": revoke });
        render(UserPage);

        await fireEvent.click(
            await screen.findByRole("button", { name: "Remove from Alpha" }),
        );
        let dialog = await screen.findByRole("dialog", {
            name: "Remove alice from Alpha?",
        });
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Cancel" }),
        );
        expect(revoke).not.toHaveBeenCalled();

        await fireEvent.click(
            await screen.findByRole("button", { name: "Remove from Alpha" }),
        );
        dialog = await screen.findByRole("dialog", {
            name: "Remove alice from Alpha?",
        });
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Remove" }),
        );
        await vi.waitFor(() => expect(revoke).toHaveBeenCalledTimes(1));
    });

    it.each([
        { active: true, button: "Deactivate", sent: false },
        { active: false, button: "Reactivate", sent: true },
    ])("$button sends active: $sent", async ({ active, button, sent }) => {
        const setActive = vi.fn(() => json({ ...alice, active: sent }));
        stubUser({ "PUT /api/admin/users/3/active": setActive }, [], {
            ...alice,
            active,
        });
        render(UserPage);

        await fireEvent.click(
            await screen.findByRole("button", { name: button }),
        );
        // Reactivate is not destructive, so only Deactivate opens a danger modal.
        if (active) {
            const dialog = await screen.findByRole("dialog", {
                name: "Deactivate alice?",
            });
            await fireEvent.click(
                within(dialog).getByRole("button", { name: "Deactivate" }),
            );
        }
        await vi.waitFor(() =>
            expect(setActive).toHaveBeenCalledWith({ active: sent }),
        );
    });

    it("shows a refused password in the Set password modal", async () => {
        stubUser({
            "PUT /api/admin/users/3/password": () =>
                json(
                    {
                        detail: {
                            code: "weak_password",
                            message: "Password must be at least 15 characters",
                        },
                    },
                    400,
                ),
        });
        render(UserPage);

        await fireEvent.click(
            await screen.findByRole("button", { name: "Set password" }),
        );
        const dialog = await screen.findByRole("dialog");
        await fireEvent.input(within(dialog).getByLabelText("New password"), {
            target: { value: "short" },
        });
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Set password" }),
        );

        expect(
            await within(dialog).findByText(
                "Password must be at least 15 characters",
            ),
        ).toBeInTheDocument();
    });
});
