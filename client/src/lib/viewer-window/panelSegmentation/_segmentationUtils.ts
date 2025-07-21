import type { Creator } from "$lib/datamodel/creator.svelte";
import { data } from "$lib/datamodel/model";
import type { DialogueType } from "$lib/types";
import { colors } from "$lib/viewer/overlays/colors";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { type Writable } from "svelte/store";

export const macularLayers = {
    background: 0,
    NFL: 1,
    GCL: 2,
    IPL: 3,
    INL: 4,
    OPL: 5,
    ONL: 6,
    ELM: 7,
    MZ: 8,
    EZ: 9,
    OS: 10,
    IDZ: 11,
    RPE: 12,
    choroid: 13,
    other: 14
}
export const layerThicknesses = {
    background: 0,
    NFL: 70,
    GCL: 30,
    IPL: 30,
    INL: 30,
    OPL: 30,
    ONL: 70,
    ELM: 5,
    MZ: 10,
    EZ: 10,
    OS: 15,
    IDZ: 10,
    RPE: 15,
    choroid: 150,
    other: 10
};



export const featureLabels: { [featureName: string]: { [layerName: string]: number } } = {
    'Macular layers': {
        background: 0,
        NFL: 1,
        GCL: 2,
        IPL: 3,
        INL: 4,
        OPL: 5,
        ONL: 6,
        ELM: 7,
        MZ: 8,
        EZ: 9,
        OS: 10,
        IDZ: 11,
        RPE: 12,
        choroid: 13,
        other: 14,

    },
    'Optic disc features': {
        background: 0,
        RNFL: 1,
        BM: 2,
        LC: 3,
        Vessel: 4,
        PPAalpha: 5,
        PPAbeta: 6,
        PPAgamma: 7
    }
};


export async function createMaskedAnnotation(dialogue: Writable<DialogueType>,
    annotation: Annotation,
    creator: Creator,
    scanNr: number,
) {
    const { annotationTypes, features } = data;
    const annotationType = annotationTypes.find(
        (a) => a.name == 'Segmentation 2D masked' && a.interpretation == 'R/G mask'
    );
    if (!annotationType) {
        dialogue.set('No annotation type found for Segmentation 2D masked + R/G mask');
        return;
    }
    const feature = features.find((f) => f.name == 'Arteriovenous (AV) branches');
    if (!feature) {
        dialogue.set('No feature found for Arteriovenous (AV) branches');
        return;
    }
    // const scanNr = $index;
    const value = {
        maskID: annotation.id,
        branches: []
    };

    dialogue.set(`Creating annotation`);

    const new_annotation = await Annotation.createFrom(
        annotation.instance!,
        feature,
        creator,
        annotationType
    );
    dialogue.set(`creating annotation data...`);

    const item = {
        annotation: new_annotation,
        scanNr: scanNr,
        mediaType: 'application/json'
    };
    const annotationData = await AnnotationData.create(item);
    dialogue.set(`uploading annotation data...`);

    await annotationData.value.setValue(value);

    dialogue.set(undefined);
}

export async function deleteAnnotation(dialogue: Writable<DialogueType>,
    annotation: Annotation,
    removeCallback: () => void) {
    const { annotations, annotationData } = data;

    const hide = () => dialogue.set(undefined);
    const reject = hide;
    const resolve = async () => {
        dialogue.set(`Deleting annotation ${annotation.id}`);

        // remove all annotationData
        // currently does not remove them from server / database
        annotation.annotationData.forEach((annotationData) => annotationData.delete(false));

        // remove from database on server
        await annotation.delete();
        // remove drawing
        removeCallback();
        hide();
    };
    const d = {
        query: `Delete annotation ${annotation.id}?`,
        approve: 'Delete',
        decline: 'Cancel',
        resolve,
        reject
    };
    dialogue.set(d);
}

export async function addBranch(dialogue: Writable<DialogueType>,
    annotationData: AnnotationData,
    image: AbstractImage,
    vesselType: 'Artery' | 'Vein' | 'Vessel') {

    const value = await annotationData.value.load();
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const drawing = canvas.toDataURL();

    const branch_ids = new Set(value.branches.map((b) => b.id));
    let i = 0;
    let branch_id = `${vesselType}_${i}`;
    while (branch_ids.has(branch_id)) {
        i++;
        branch_id = `${vesselType}_${i}`;
    }
    const branch = {
        id: branch_id,
        vesselType,
        drawing,
        color: colors[value.branches.length % colors.length]
    };
    value.branches.push(branch);
    dialogue.set(`Updating data for ${annotationData.id}...`);
    await annotationData.value.setValue(value);
    dialogue.set(undefined);
}