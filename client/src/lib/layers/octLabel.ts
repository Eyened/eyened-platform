import { instances } from "$lib/data/stores.svelte";

// AnatomicRegion codes, as the DICOM export reads them.
// ASSUMPTION: other codes (0, 3, 15 on the dev data) have no known name, so they add no word.
const REGIONS: Record<string, string> = { "1": "disc", "2": "macula" };

/** "OCT 2024-03-12 · macula · 49 B-scans", with a twin number after the date; the OCT's ID when its details are not loaded. */
export function octLabel(octId: string, bscans: number, twin = ""): string {
    const meta = instances.get(octId);
    const region = REGIONS[meta?.anatomic_region ?? ""];
    const where = region ? ` · ${region}` : "";
    const date = meta?.study.date ?? octId;
    return `OCT ${twin ? `${date} ${twin}` : date}${where} · ${bscans} B-scans`;
}
