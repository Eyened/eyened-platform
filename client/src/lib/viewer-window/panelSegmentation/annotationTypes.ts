import { data } from "$lib/datamodel/model";

export function getAnnotationTypes() {
    const { annotationTypes } = data;
    const Q = annotationTypes.find(
        (t) => t.name == "Binary + Questionable",
    )!;
    const B = annotationTypes.find((t) => t.name == "Binary")!;
    const P = annotationTypes.find(
        (t) => t.name == "Probability" && t.dataType == "R8",
    )!;
    return { Q, B, P };
}