export type EyeLaterality = "L" | "R" | null;

export type OpenImage = {
    imageId: string;
    instanceId: string;
    patientId: number;
    laterality: EyeLaterality;
    studyId: number | undefined;
};

export type EyeGroup = {
    patientId: number;
    laterality: EyeLaterality;
    images: OpenImage[];
};

/** Top-row order is instance order. Images of one instance keep their relative order. */
export function orderByInstanceIds<T extends { instanceId: string }>(
    images: readonly T[],
    instanceIds: readonly string[],
): T[] {
    const rank = new Map(instanceIds.map((id, index) => [id, index]));
    return images
        .map((image, index) => ({ image, index }))
        .sort((a, b) => {
            const rankA =
                rank.get(a.image.instanceId) ?? Number.MAX_SAFE_INTEGER;
            const rankB =
                rank.get(b.image.instanceId) ?? Number.MAX_SAFE_INTEGER;
            if (rankA !== rankB) return rankA - rankB;
            return a.index - b.index;
        })
        .map(({ image }) => image);
}

export function groupOpenImages(images: readonly OpenImage[]): EyeGroup[] {
    const groups: EyeGroup[] = [];
    for (const image of images) {
        let group = groups.find(
            (g) =>
                g.patientId === image.patientId &&
                g.laterality === image.laterality,
        );
        if (!group) {
            group = {
                patientId: image.patientId,
                laterality: image.laterality,
                images: [],
            };
            groups.push(group);
        }
        group.images.push(image);
    }
    return groups;
}

export function canOpenRegistration(
    fixedId: string | null,
    movingId: string | null,
    annotationChoice: string | null,
): boolean {
    return (
        !!fixedId &&
        !!movingId &&
        fixedId !== movingId &&
        annotationChoice !== null &&
        annotationChoice !== ""
    );
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
