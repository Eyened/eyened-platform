import { afterEach, describe, expect, it, vi } from "vitest";
import { authClient } from "../auth";
import { UserManager } from "./usermanager.svelte";

const { goto } = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock("$app/navigation", () => ({ goto }));
vi.mock("$app/paths", () => ({ resolve: (route: string) => route }));

afterEach(() => {
    vi.clearAllMocks();
    history.replaceState(null, "", "/");
});

describe("UserManager.login", () => {
    it.each([
        { next: "http://eyened-gpu:1700/", expected: "/" },
        { next: `${location.origin}/tasks?page=2`, expected: "/tasks?page=2" },
    ])("redirects next=$next to $expected", async ({ next, expected }) => {
        vi.spyOn(authClient, "login").mockResolvedValue({
            id: 1,
            username: "ada",
            role: null,
            is_admin: false,
            starred_tags: [],
        });
        history.replaceState(
            null,
            "",
            `/users/login?next=${encodeURIComponent(next)}`,
        );

        await new UserManager().login("ada", "secret", false);

        expect(goto).toHaveBeenCalledWith(expected);
    });
});
