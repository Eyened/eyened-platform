import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import { json, stubFetch } from "../../../vitest-fetch";

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock("$app/navigation", () => ({ goto }));
vi.mock("$app/paths", () => ({
    resolve: (route: string, params?: Record<string, string>) =>
        route.replace(/\[(\w+)\]/g, (_, key: string) => params?.[key] ?? ""),
}));

const { default: UsersPage } = await import("./+page.svelte");

afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
});

async function submitCreate() {
    await fireEvent.input(screen.getByLabelText("Username"), {
        target: { value: "alice" },
    });
    await fireEvent.input(screen.getByLabelText("Password"), {
        target: { value: "correct-horse-battery" },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Create user" }));
}

describe("users page", () => {
    it("opens the new user after creating them", async () => {
        const create = vi.fn(() =>
            json(
                {
                    id: 7,
                    username: "alice",
                    is_admin: false,
                    active: true,
                    has_credential: true,
                    employee_identifier: null,
                },
                201,
            ),
        );
        stubFetch({
            "GET /api/admin/users": () => json([]),
            "POST /api/admin/users": create,
        });
        render(UsersPage);

        await submitCreate();

        await vi.waitFor(() =>
            expect(goto).toHaveBeenCalledWith("/admin/users/7"),
        );
        expect(create).toHaveBeenCalledWith({
            username: "alice",
            password: "correct-horse-battery",
        });
    });

    it("shows the server's reason when creation is refused", async () => {
        stubFetch({
            "GET /api/admin/users": () => json([]),
            "POST /api/admin/users": () =>
                json(
                    {
                        detail: {
                            code: "username_taken",
                            message: "alice already exists",
                        },
                    },
                    409,
                ),
        });
        render(UsersPage);

        await submitCreate();

        expect(
            await screen.findByText("alice already exists"),
        ).toBeInTheDocument();
        expect(goto).not.toHaveBeenCalled();
    });
});
