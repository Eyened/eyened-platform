import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";

const { pageState } = vi.hoisted(() => ({
    pageState: { url: new URL("http://localhost/") },
}));

vi.mock("$app/paths", () => ({ resolve: (path: string) => path }));
vi.mock("$app/state", () => ({ page: pageState }));

vi.mock(
    "$lib/components/Main.svelte",
    async () => import("../../../vitest-passthrough.svelte"),
);

const { default: TopMenu } = await import("$lib/components/TopMenu.svelte");
const { default: AdminLayout } = await import("./+layout.svelte");

function context(is_admin: boolean) {
    return new Map([
        [
            "globalContext",
            { userManager: { user: { username: "u", is_admin } } },
        ],
    ]);
}

const children = createRawSnippet(() => ({
    render: () => "<p>admin body</p>",
}));

describe("admin gate", () => {
    it("shows the Admin link to admins only", () => {
        render(TopMenu, { context: context(true) });
        expect(screen.getByText("Admin")).toBeInTheDocument();
        document.body.innerHTML = "";
        render(TopMenu, { context: context(false) });
        expect(screen.queryByText("Admin")).toBeNull();
    });

    it("marks the section of the current page", () => {
        pageState.url = new URL("http://localhost/tasks/12");
        render(TopMenu, { context: context(true) });
        expect(screen.getByRole("link", { name: "Tasks" })).toHaveAttribute(
            "aria-current",
            "page",
        );
        expect(
            screen.getByRole("link", { name: "Browser" }),
        ).not.toHaveAttribute("aria-current");
        expect(screen.getByRole("link", { name: "Admin" })).not.toHaveAttribute(
            "aria-current",
        );
    });

    it("renders the admin pages for admins only", () => {
        render(AdminLayout, { props: { children }, context: context(true) });
        expect(screen.getByText("admin body")).toBeInTheDocument();
        document.body.innerHTML = "";
        render(AdminLayout, { props: { children }, context: context(false) });
        expect(screen.getByText("Not authorised")).toBeInTheDocument();
        expect(screen.queryByText("admin body")).toBeNull();
    });
});
