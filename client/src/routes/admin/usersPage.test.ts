import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/svelte";
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

function user(id: number, username: string) {
    return {
        id,
        username,
        is_admin: false,
        active: true,
        has_credential: true,
        employee_identifier: null,
    };
}

async function submitCreate() {
    await fireEvent.click(
        await screen.findByRole("button", { name: "Create user" }),
    );
    const dialog = await screen.findByRole("dialog");
    await fireEvent.input(within(dialog).getByLabelText("Username"), {
        target: { value: "alice" },
    });
    await fireEvent.input(within(dialog).getByLabelText("Password"), {
        target: { value: "correct-horse-battery" },
    });
    await fireEvent.click(
        within(dialog).getByRole("button", { name: "Create user" }),
    );
    return dialog;
}

describe("users page", () => {
    it("opens the new user after creating them", async () => {
        const create = vi.fn(() => json(user(7, "alice"), 201));
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

    it("shows the server's reason in the modal when creation is refused", async () => {
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

        const dialog = await submitCreate();

        expect(
            await within(dialog).findByText("alice already exists"),
        ).toBeInTheDocument();
        expect(goto).not.toHaveBeenCalled();
    });

    it("pages the search results and starts a new search on page 1", async () => {
        const users = Array.from({ length: 25 }, (_, i) =>
            user(i + 1, `user${String(i + 1).padStart(2, "0")}`),
        );
        stubFetch({ "GET /api/admin/users": () => json(users) });
        render(UsersPage);

        expect(await screen.findByText("user20")).toBeInTheDocument();
        expect(screen.queryByText("user21")).toBeNull();
        await fireEvent.click(
            screen.getByRole("button", { name: "Next page" }),
        );
        expect(screen.getByText("user25")).toBeInTheDocument();

        await fireEvent.input(screen.getByLabelText("Search users"), {
            target: { value: "user0" },
        });
        expect(screen.getByText("user01")).toBeInTheDocument();
        expect(screen.queryByText("user10")).toBeNull();
    });
});
