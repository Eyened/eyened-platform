import type { Annotation } from "./annotation";
import type { Instance } from "./instance";
import { ItemConstructor } from "./itemContructor";
import type { Item } from "./itemList";
import { FKMapping } from "./mapping";
import type { Study } from "./study";

export interface Tag extends Item {
    id: number,
    name: string,
}
export const TagConstructor = new ItemConstructor<Tag>('TagID', { name: 'TagName' });

export interface InstanceTag extends Item {
    id: string,
    instance: Instance,
    tag: Tag,
}
export const InstanceTagConstructor = new ItemConstructor<InstanceTag>(
    params => `${params.ImageInstanceID}_${params.TagID}`, {
    instance: FKMapping('ImageInstanceID', 'instances'),
    tag: FKMapping('TagID', 'tags')
});

export interface StudyTag extends Item {
    id: string,
    study: Study,
    tag: Tag,
}
export const StudyTagConstructor = new ItemConstructor<StudyTag>(
    params => `${params.StudyID}_${params.TagID}`, {
    study: FKMapping('StudyID', 'studies'),
    tag: FKMapping('TagID', 'tags')
});

export interface AnnotationTag extends Item {
    id: string
    annotation: Annotation,
    tag: Tag,
}
export const AnnotationTagConstructor = new ItemConstructor<AnnotationTag>(
    params => `${params.AnnotationID}_${params.TagID}`, {
    annotation: FKMapping('AnnotationID', 'annotations'),
    tag: FKMapping('TagID', 'tags')
});
