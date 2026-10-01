import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("$lib/data/api", () => ({
    searchStudies: vi.fn(),
}));

const { searchStudies } = await import("$lib/data/api");
const { clearPatientStudyCache, loadPatientStudies } = await import(
    "./patientStudies"
);

const older = { id: 1, date: "2019-01-01" };
const newer = { id: 2, date: "2024-05-01" };

describe("loadPatientStudies", () => {
    beforeEach(() => {
        clearPatientStudyCache();
        vi.mocked(searchStudies).mockReset();
    });

    it("loads a patient's studies newest first", async () => {
        vi.mocked(searchStudies).mockResolvedValue({
            studies: [older, newer],
            has_more: false,
        });

        const result = await loadPatientStudies("P1");

        expect(searchStudies).toHaveBeenCalledWith({
            conditions: [
                {
                    variable: "Patient Identifier",
                    operator: "==",
                    value: "P1",
                },
            ],
            limit: 200,
            page: 0,
            order_by: "Study Date",
            order: "DESC",
            include_count: true,
        });
        expect(result.studies.map((study) => study.id)).toEqual([2, 1]);
        expect(result.truncated).toBe(false);
    });

    it("reports when the search stopped before the oldest visit", async () => {
        vi.mocked(searchStudies).mockResolvedValue({
            studies: [newer],
            has_more: true,
        });

        const result = await loadPatientStudies("P1");

        expect(result.truncated).toBe(true);
    });

    it("reuses the loaded list for the same patient", async () => {
        vi.mocked(searchStudies).mockResolvedValue({
            studies: [newer],
            has_more: false,
        });

        await loadPatientStudies("P1");
        await loadPatientStudies("P1");

        expect(searchStudies).toHaveBeenCalledTimes(1);
    });
});
