import { beforeEach, describe, expect, it, vi } from "vitest";
import { tick } from "svelte";
import { fireEvent, render, screen } from "@testing-library/svelte";
import type { StudyGET } from "../../../types/openapi_types";

const { loadPatientStudies } = vi.hoisted(() => ({
    loadPatientStudies: vi.fn(),
}));

vi.mock("./patientStudies", () => ({
    loadPatientStudies,
}));

vi.mock("$lib/extensions", () => ({
    default: {
        viewer: {
            panel_info: {
                additional_data_sources: [
                    {
                        name: "External grades",
                        url: "/external",
                        conditions: [],
                    },
                ],
            },
        },
    },
}));

vi.mock("$lib/browser/dataSources", async (importOriginal) => {
    const actual =
        await importOriginal<typeof import("$lib/browser/dataSources")>();
    return {
        ...actual,
        loadDataSource: vi.fn(async () => ({ Scores: [] })),
    };
});

const { default: PanelVisits } = await import("./PanelVisits.svelte");

function study(id: number, date: string): StudyGET {
    return {
        id,
        date,
        project: { name: "RS" },
        patient: { id: 1, identifier: "P1" },
        series: [],
        tags: [],
    } as unknown as StudyGET;
}

const current = study(10, "2024-06-01");
const earlier = study(11, "2020-01-01");

const context = new Map<string, unknown>([
    [
        "viewerContext",
        {
            image: {
                instance: {
                    patient: { id: 1, identifier: "P1" },
                    study: { id: 10 },
                },
            },
        },
    ],
]);

describe("PanelVisits", () => {
    beforeEach(() => {
        loadPatientStudies.mockReset();
        loadPatientStudies.mockResolvedValue({
            studies: [current, earlier],
            truncated: false,
        });
    });

    it("does not search while Info is collapsed", async () => {
        render(PanelVisits, { props: { active: false }, context });
        await tick();
        expect(loadPatientStudies).not.toHaveBeenCalled();
    });

    it("opens grading for the current visit and keeps other visits folded", async () => {
        render(PanelVisits, { props: { active: true }, context });

        expect(
            await screen.findByRole("button", { name: /2024-06-01/ }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /2020-01-01/ }),
        ).toBeInTheDocument();
        expect(screen.getByText("this visit")).toBeInTheDocument();
        expect(
            screen.queryByRole("heading", { name: "Visit grades" }),
        ).not.toBeInTheDocument();
        expect(
            await screen.findAllByRole("heading", { name: /External grades/ }),
        ).toHaveLength(1);

        await fireEvent.click(
            screen.getByRole("button", { name: /2020-01-01/ }),
        );

        expect(
            await screen.findAllByRole("heading", { name: /External grades/ }),
        ).toHaveLength(2);
    });
});
