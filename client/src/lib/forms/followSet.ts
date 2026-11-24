import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../types/openapi_types";
import { matchForms, type FormTarget, type OpenImage } from "./formTargets";

export type Arrival =
    | { kind: "form"; form: FormAnnotationGET; target: FormTarget }
    | { kind: "grade"; target: FormTarget; image: OpenImage }
    | { kind: "nothing" };

/** What the window shows on arriving at a set: Grading's task row for the remembered schema and the selected viewport's image, as its form, Grade, or nothing. */
export function followSet(input: {
    schema: FormSchemaGET;
    images: readonly OpenImage[];
    selectedImageId: string | null;
    forms: Iterable<FormAnnotationGET>;
    userId: number;
    subTaskId: number;
}): Arrival {
    const { schema, images } = input;
    const image = images.find((i) => i.imageId === input.selectedImageId);
    if (!image) return { kind: "nothing" };
    // The same rule as Grading's task rows, with the remembered schema as the task's.
    const { taskRows } = matchForms({
        forms: input.forms,
        images,
        schemas: new Map([[schema.id, schema]]),
        taskSchemaId: schema.id,
        userId: input.userId,
        subTaskId: input.subTaskId,
    });
    const row = taskRows!.find((r) =>
        r.target.imageIds.includes(image.imageId),
    )!;
    return row.form
        ? { kind: "form", form: row.form, target: row.target }
        : { kind: "grade", target: row.target, image };
}
