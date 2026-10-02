import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";

const { loadPatientStudies } = vi.hoisted(() => ({
    loadPatientStudies: vi.fn(),
}));

vi.mock("../panelVisits/patientStudies", () => ({
    loadPatientStudies,
}));

vi.mock("$lib/extensions", () => ({
    default: {
        viewer: {
            panel_info: {
                additional_data_sources: [],
            },
        },
    },
}));

const { default: PanelInfo } = await import("./panelInfo.svelte");

const context = new Map<string, unknown>([
    [
        "viewerContext",
        {
            image: {
                instance: {
                    patient: { identifier: "P1" },
                    study: { id: 10, date: "2024-06-01" },
                    modality: "CF",
                    laterality: "R",
                },
            },
        },
    ],
]);

describe("PanelInfo", () => {
    beforeEach(() => {
        loadPatientStudies.mockReset();
        loadPatientStudies.mockResolvedValue({
            studies: [
                {
                    id: 10,
                    date: "2024-06-01",
                    project: { name: "RS" },
                    patient: { id: 1, identifier: "P1" },
                },
            ],
            truncated: false,
        });
    });

    it("keeps image metadata and lists visits under it", async () => {
        render(PanelInfo, { props: { active: true }, context });

        expect(screen.getByText("Patient ID")).toBeInTheDocument();
        expect(screen.getByText("P1")).toBeInTheDocument();
        expect(
            await screen.findByRole("button", { name: /2024-06-01/ }),
        ).toBeInTheDocument();
        expect(screen.queryByText("Create new form")).not.toBeInTheDocument();
    });
});
