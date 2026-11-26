import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import InfoPanel from "./InfoPanel.svelte";
import { instance, workspaceContext, workspaceWith } from "./testUtils";

vi.mock("./patientStudies", () => ({
    loadPatientStudies: vi.fn(),
    PATIENT_STUDY_LIMIT: 200,
}));
vi.mock("$lib/utils/copyToClipboard", () => ({
    copyToClipboard: vi.fn(async () => true),
}));
// View all properties… stays loading; only its title's copy button is under test.
vi.mock("$lib/data/api", () => ({
    fetchInstance: vi.fn(() => new Promise(() => {})),
}));

function renderPanel() {
    render(InfoPanel, {
        props: {
            instanceFor: (id: string) => instance(id),
            subtitle: "Viewport 1 · P-000417 OD · CF F1",
            shown: false,
        },
        context: workspaceContext(workspaceWith(1)),
    });
}
const viewAll = () =>
    fireEvent.click(
        screen.getByRole("button", { name: "View all properties…" }),
    );
const close = () =>
    fireEvent.click(screen.getByRole("button", { name: "Close" }));

describe("InfoPanel", () => {
    it("copying a value says so in the panel's status; the button keeps its name", async () => {
        render(InfoPanel, {
            props: {
                instanceFor: (id: string) => instance(id),
                subtitle: "Viewport 1 · P-000417 OD · CF F1",
                shown: false,
            },
            context: workspaceContext(workspaceWith(1)),
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Copy Patient ID" }),
        );
        // By text: Visits' loading indicator may be a status region too.
        expect(await screen.findByText("Patient ID copied")).toHaveAttribute(
            "role",
            "status",
        );
        expect(
            screen.getByRole("button", { name: "Copy Patient ID" }),
        ).toBeInTheDocument();
    });

    describe("View all properties…", () => {
        afterEach(() => {
            vi.useRealTimers();
        });

        it("Copied! is gone when the dialog opens again", async () => {
            renderPanel();
            await viewAll();
            await fireEvent.click(
                screen.getByRole("button", { name: "Copy public ID" }),
            );
            expect(
                await screen.findByRole("button", { name: "Copied!" }),
            ).toBeInTheDocument();
            await close();
            await viewAll();
            expect(
                screen.getByRole("button", { name: "Copy public ID" }),
            ).toBeInTheDocument();
        });

        it("a copy from before the close doesn't cut a later Copied! short", async () => {
            vi.useFakeTimers();
            renderPanel();
            await viewAll();
            await fireEvent.click(
                screen.getByRole("button", { name: "Copy public ID" }),
            );
            await vi.advanceTimersByTimeAsync(0);
            await close();
            await vi.advanceTimersByTimeAsync(500);
            await viewAll();
            await fireEvent.click(
                screen.getByRole("button", { name: /Copy public ID|Copied!/ }),
            );
            // 2.1 s after the first copy, 1.6 s after the second.
            await vi.advanceTimersByTimeAsync(1600);
            expect(
                screen.getByRole("button", { name: "Copied!" }),
            ).toBeInTheDocument();
        });
    });
});
