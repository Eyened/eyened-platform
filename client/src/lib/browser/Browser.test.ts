import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import type {
    SearchCondition,
    SignatureField,
} from "../../types/openapi_types";

const { goto, pageState } = vi.hoisted(() => ({
    goto: vi.fn(),
    pageState: { url: new URL("http://localhost/") },
}));
vi.mock("$app/navigation", () => ({ goto, afterNavigate: vi.fn() }));
vi.mock("$app/environment", () => ({ browser: true }));
vi.mock("$app/state", () => ({ page: pageState }));
vi.mock("$lib/data/api", async (importOriginal) => ({
    ...(await importOriginal<typeof import("$lib/data/api")>()),
    getInstancesSignature: vi.fn(),
    getStudiesSignature: vi.fn(),
    searchInstances: vi.fn(),
    searchStudies: vi.fn(),
}));

const api = await import("$lib/data/api");
const { BrowserContext, encodeConditions } = await import(
    "./browserContext.svelte"
);
const { default: Browser } = await import("./Browser.svelte");

const field = (
    name: string,
    values: SignatureField["values"],
    extra: Partial<SignatureField> = {},
): SignatureField => ({
    name,
    values,
    type: "default",
    nullable: false,
    multi: false,
    ...extra,
});
const SIGNATURE = [
    field("Patient Identifier", "string", { multi: true }),
    field("Study Date", "date"),
    field("Project Name", ["Alpha", "Beta"]),
];

const patientCondition = {
    type: "default",
    variable: "Patient Identifier",
    operator: "==",
    value: "P1",
} as SearchCondition;

const response = (ids: number[]) => ({
    result_ids: ids,
    count: ids.length,
    studies: [],
    instances: [],
});

const urlWithConditions = () => {
    const url = new URL("http://localhost/");
    url.searchParams.set("conditions", encodeConditions([patientCondition]));
    return url;
};
const toggle = () => screen.getByRole("button", { name: /^Filters/ });

beforeEach(() => {
    goto.mockReset();
    pageState.url = new URL("http://localhost/");
    vi.mocked(api.getStudiesSignature).mockResolvedValue(SIGNATURE);
    vi.mocked(api.getInstancesSignature).mockResolvedValue(SIGNATURE);
    vi.mocked(api.searchStudies).mockReset();
    vi.mocked(api.searchInstances).mockReset();
});

describe("Browser", () => {
    it("opens the filters and prompts for a search when the URL has no conditions", async () => {
        render(Browser, { props: { context: new BrowserContext() } });

        expect(toggle().getAttribute("aria-expanded")).toBe("true");
        expect(screen.getByText("Search for images")).toBeTruthy();
        await waitFor(() =>
            expect(document.activeElement).toBe(
                screen.getByLabelText(/patient/i, { selector: "input" }),
            ),
        );
        expect(api.searchStudies).not.toHaveBeenCalled();
    });

    it("searches the URL's conditions, collapses the filters and re-searches on submit", async () => {
        pageState.url = urlWithConditions();
        vi.mocked(api.searchStudies).mockResolvedValue(response([1, 2]));
        const { container } = render(Browser, {
            props: { context: new BrowserContext() },
        });

        await screen.findByText("2 studies");
        expect(api.searchStudies).toHaveBeenCalledTimes(1);
        expect(toggle().getAttribute("aria-expanded")).toBe("false");
        expect(toggle().textContent).toContain("Filters (1)");
        expect(
            screen.getByRole("button", { name: "Clear filters" }),
        ).toBeTruthy();
        expect(screen.getByText(/items? per page/i)).toBeTruthy();

        await fireEvent.submit(
            container.querySelector("form#browser-filters")!,
        );

        await waitFor(() => expect(api.searchStudies).toHaveBeenCalledTimes(2));
        expect(toggle().getAttribute("aria-expanded")).toBe("false");
    });

    it("keeps the filters open and shows the notification when the search fails", async () => {
        pageState.url = urlWithConditions();
        vi.mocked(api.searchStudies).mockRejectedValue(
            new Error("Bad gateway"),
        );
        render(Browser, { props: { context: new BrowserContext() } });

        expect(await screen.findByText("Search failed")).toBeTruthy();
        expect(toggle().getAttribute("aria-expanded")).toBe("true");
    });

    it("searches images and counts them after switching to Images", async () => {
        pageState.url = urlWithConditions();
        vi.mocked(api.searchStudies).mockResolvedValue(response([1, 2]));
        vi.mocked(api.searchInstances).mockResolvedValue(response([5, 6, 7]));
        render(Browser, { props: { context: new BrowserContext() } });
        await screen.findByText("2 studies");

        await fireEvent.click(screen.getByRole("tab", { name: "Images" }));

        await screen.findByText("3 images");
        expect(api.searchInstances).toHaveBeenCalled();
    });

    it("searches the initial conditions at mount in an overlay without URL sync", async () => {
        vi.mocked(api.searchStudies).mockResolvedValue(response([1]));
        render(Browser, {
            props: {
                context: new BrowserContext(),
                mode: "overlay",
                syncUrl: false,
                initialConditions: [patientCondition],
            },
        });

        await screen.findByText("1 study");
        expect(api.searchStudies).toHaveBeenCalledTimes(1);
        expect(goto).not.toHaveBeenCalled();
    });
});
