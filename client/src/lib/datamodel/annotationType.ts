import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";

export interface AnnotationType extends Item {
    id: number,
    name: string,
    interpretation: 'Binary mask' | 'Probability' | 'R/G mask' | 'Label numbers' | 'Layer bits',
}

export const AnnotationTypeConstructor = new ItemConstructor<AnnotationType>(
    'AnnotationTypeID', {
    name: 'AnnotationTypeName',
    interpretation: 'Interpretation'
});