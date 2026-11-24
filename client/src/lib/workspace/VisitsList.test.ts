import { render, screen } from "@testing-library/svelte";
import { tick } from "svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StudyGET } from "../../types/openapi_types";
import { instance } from "./testUtils";

const { loadPatientStudies } = vi.hoisted(() => ({
    loadPatientStudies: vi.fn(),
}));
vi.mock("./patientStudies", () => ({
    loadPatientStudies,
    PATIENT_STUDY_LIMIT: 200,
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
vi.mock("$lib/browser/dataSources", async (importOriginal) => ({
    ...(await importOriginal<typeof import("$lib/browser/dataSources")>()),
    loadDataSource: vi.fn(async () => ({ Scores: [] })),
}));

const { default: VisitsList } = await import("./VisitsList.svelte");

function study(id: number, date: string, identifier = "P1"): StudyGET {
    return {
        id,
        date,
        project: { id: 1, name: "RS" },
        patient: { id: 1, identifier },
        series: [],
        tags: [],
    } as unknown as StudyGET;
}
const current = study(10, "2024-06-01");
const earlier = study(11, "2020-01-01");
const p1 = instance("a", {
    patient: { id: 1, identifier: "P1" },
    study: { id: 10, date: "2024-06-01" },
});

describe("VisitsList", () => {
    beforeEach(() => {
        loadPatientStudies.mockReset();
        loadPatientStudies.mockImplementation(async (id: string) =>
            id === "P1"
                ? { studies: [current, earlier], truncated: false }
                : {
                      studies: [study(21, "2022-02-02", "P2")],
                      truncated: false,
                  },
        );
    });

    it("searches only once Info is shown", async () => {
        const { rerender } = render(VisitsList, {
            props: { instance: p1, active: false },
        });
        await tick();
        expect(loadPatientStudies).not.toHaveBeenCalled();
        await rerender({ instance: p1, active: true });
        expect(loadPatientStudies).toHaveBeenCalledWith("P1");
    });

    it("opens this visit, marked as such, with its data sources", async () => {
        render(VisitsList, { props: { instance: p1, active: true } });
        expect(
            await screen.findByRole("button", { name: /2024-06-01/ }),
        ).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByText("This visit")).toBeInTheDocument();
        expect(
            await screen.findAllByRole("heading", {
                name: /External grades/,
                level: 5,
            }),
        ).toHaveLength(1);
    });

    it("another patient's image reloads the list with that image's visit open", async () => {
        const { rerender } = render(VisitsList, {
            props: { instance: p1, active: true },
        });
        await screen.findByRole("button", { name: /2024-06-01/ });
        await rerender({
            instance: instance("b", {
                patient: { id: 2, identifier: "P2" },
                study: { id: 21, date: "2022-02-02" },
            }),
            active: true,
        });
        expect(
            await screen.findByRole("button", { name: /2022-02-02/ }),
        ).toHaveAttribute("aria-expanded", "true");
        expect(loadPatientStudies).toHaveBeenLastCalledWith("P2");
    });

    it("a failed load says so without the patient ID", async () => {
        loadPatientStudies.mockRejectedValue(
            new Error("POST /api/studies/search P1 failed"),
        );
        render(VisitsList, { props: { instance: p1, active: true } });
        expect(
            await screen.findByText("Visits couldn't be loaded"),
        ).toBeInTheDocument();
        expect(screen.queryByText(/P1/)).toBeNull();
    });
});
