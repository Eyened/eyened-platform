import { BaseItem } from "./baseItem";
import type { Instance } from "./instance.svelte";
import { data, registerConstructor } from "./model";
import type { Study } from "./study";

export interface ServerTag {
    TagID: number;
    TagName: string;
}
export interface ServerInstanceTag {
    ImageInstanceID: number;
    TagID: number;
}
export interface ServerStudyTag {
    StudyID: number;
    TagID: number;
}
export interface ServerAnnotationTag {
    AnnotationID: number;
    TagID: number;
}

export class Tag extends BaseItem {
    static endpoint = 'tags';
    static mapping = {
        'TagName': 'name',
    };
    id!: number;
    name!: string;
    constructor(item: ServerTag) {
        super();
        this.init(item);
    }
    init(item: ServerTag) {
        this.id = item.TagID;
        this.name = item.TagName;
    }
}
registerConstructor('tags', Tag);

export class InstanceTag extends BaseItem {
    static endpoint = 'instance-tags';
    static mapping = {
        'ImageInstanceID': 'instanceId',
        'TagID': 'tagId',
    };
    id!: string;
    instanceId!: number;
    tagId!: number;
    constructor(item: ServerInstanceTag) {
        super();
        this.init(item);
    }
    init(item: ServerInstanceTag) {
        this.id = `${item.ImageInstanceID}_${item.TagID}`;
        this.instanceId = item.ImageInstanceID;
        this.tagId = item.TagID;
    }
    get instance(): Instance {  
        return data.instances.get(this.instanceId)!;
    }
}
registerConstructor('instance-tags', InstanceTag);

export class StudyTag extends BaseItem {
    static endpoint = 'study-tags';
    static mapping = {
        'StudyID': 'studyId',
        'TagID': 'tagId',
    };
    id!: string;
    studyId!: number;
    tagId!: number;
    constructor(item: ServerStudyTag) {
        super();
        this.init(item);
    }
    init(item: ServerStudyTag) {
        this.id = `${item.StudyID}_${item.TagID}`;
        this.studyId = item.StudyID;
        this.tagId = item.TagID;
    }
    get study(): Study {
        return data.studies.get(this.studyId)!;
    }
    get tag(): Tag {
        return data.tags.get(this.tagId)!;
    }
}
registerConstructor('study-tags', StudyTag);

export class AnnotationTag extends BaseItem {
    static endpoint = 'annotation-tags';
    static mapping = {
        'AnnotationID': 'annotationId',
        'TagID': 'tagId',
    };
    id!: string;
    annotationId!: number;
    tagId!: number;
    constructor(item: ServerAnnotationTag) {
        super();
        this.init(item);
    }
    init(item: ServerAnnotationTag) {
        this.id = `${item.AnnotationID}_${item.TagID}`;
        this.annotationId = item.AnnotationID;
        this.tagId = item.TagID;
    }

}
registerConstructor('annotation-tags', AnnotationTag);