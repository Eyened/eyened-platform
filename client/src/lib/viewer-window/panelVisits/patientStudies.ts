import { searchStudies } from "$lib/data/api";
import type { StudyGET, StudySearchQuery } from "../../../types/openapi_types";

/** Matches the study-search default. Older visits beyond this are not listed. */
export const PATIENT_STUDY_LIMIT = 200;

export type PatientStudies = {
    studies: StudyGET[];
    truncated: boolean;
};

const cache = new Map<string, Promise<PatientStudies>>();

export function clearPatientStudyCache() {
    cache.clear();
}

export function loadPatientStudies(
    identifier: string,
): Promise<PatientStudies> {
    const cached = cache.get(identifier);
    if (cached) return cached;

    const pending = fetchPatientStudies(identifier);
    cache.set(identifier, pending);
    pending.catch(() => {
        if (cache.get(identifier) === pending) cache.delete(identifier);
    });
    return pending;
}

async function fetchPatientStudies(
    identifier: string,
): Promise<PatientStudies> {
    const query: StudySearchQuery = {
        conditions: [
            {
                variable: "Patient Identifier",
                operator: "==",
                value: identifier,
            },
        ],
        limit: PATIENT_STUDY_LIMIT,
        page: 0,
        order_by: "Study Date",
        order: "DESC",
        include_count: true,
    };
    const data = await searchStudies(query);
    const studies = [...(data.studies ?? [])].sort(
        (a: StudyGET, b: StudyGET) =>
            new Date(b.date).getTime() - new Date(a.date).getTime(),
    );
    return { studies, truncated: Boolean(data.has_more) };
}
