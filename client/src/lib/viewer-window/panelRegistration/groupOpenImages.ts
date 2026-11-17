export type EyeLaterality = "L" | "R" | null;

export function groupKey(patientId: number, laterality: EyeLaterality): string {
    return `${patientId}:${laterality ?? "unset"}`;
}

export function annotationMatchesEye(
    annotation: {
        form_schema_id: number;
        patient_id?: number | null;
        laterality?: EyeLaterality;
        image_id?: string | null;
    },
    schemaId: number,
    patientId: number,
    laterality: EyeLaterality,
    imageLaterality: (imageId: string) => EyeLaterality | undefined,
): boolean {
    if (annotation.form_schema_id !== schemaId) return false;
    if (annotation.patient_id !== patientId) return false;
    const fromImage =
        annotation.image_id != null
            ? imageLaterality(annotation.image_id)
            : undefined;
    const formLaterality = annotation.laterality ?? fromImage ?? null;
    return formLaterality === laterality;
}
