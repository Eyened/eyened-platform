import { apiUrl } from "$lib/config";
import { decodeNpy, type NPYArray } from "$lib/utils/npy_loader";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { BaseItem, toServer } from "./baseItem";
import type { CompositeFeature } from "./compositeFeature.svelte";
import type { Creator } from "./creator.svelte";
import type { Feature } from "./feature.svelte";
import type { Instance } from "./instance.svelte";
import { FilterList } from "./itemList";
import { data, importData, registerConstructor } from "./model";
import type { Study } from "./study";


export type SimpleDataRepresentation = 'Binary' | 'DualBitMask' | 'Probability';
export type DataRepresentation = SimpleDataRepresentation | 'MultiLabel' | 'MultiClass';
export type Datatype = 'R8' | 'R8UI' | 'R16UI' | 'R32UI' | 'R32F';

export interface ServerSegmentation {
    SegmentationID: number,
    ImageInstanceID: number,
    FeatureID: number,
    CreatorID: number,
    DataType: Datatype,
    DataRepresentation: DataRepresentation,
    Threshold: number,
    ReferenceSegmentationID: number | null,
    ZarrArrayIndex: number,
    Depth: number,
    Height: number,
    Width: number,
    SparseAxis: number | null,
    ImageProjectionMatrix: number[][],
    ScanIndices: number[],
    DateInserted: string,
    DateModified: string | null,
    Inactive: boolean,
}

export class Segmentation extends BaseItem {

    static endpoint = 'segmentations';
    static mapping = {
        'ImageInstanceID': 'instanceId',
        'FeatureID': 'featureId',
        'CreatorID': 'creatorId',
        'DataType': 'dataType',
        'DataRepresentation': 'dataRepresentation',
        'Depth': 'depth',
        'Height': 'height',
        'Width': 'width',
        'SparseAxis': 'sparseAxis',
        'ImageProjectionMatrix': 'imageProjectionMatrix',
        'ScanIndices': 'scanIndices',
        'ReferenceSegmentationID': 'referenceId',
        'Threshold': 'threshold',
        'ZarrArrayIndex': 'zarrArrayIndex',
        'DateInserted': 'dateInserted',
        'DateModified': 'dateModified',
        'Inactive': 'inactive',
    };

    id!: number;
    instanceId: number = 0;
    featureId: number = 0;
    creatorId: number = 0;
    dataType: Datatype = 'R8UI';
    dataRepresentation: DataRepresentation = 'Binary';
    threshold: number = $state(0.5);
    referenceId: number | null = $state(null);
    depth: number = 0;
    height: number = 0;
    width: number = 0;
    sparseAxis: number | null = null;
    imageProjectionMatrix: number[][] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    scanIndices: number[] | null = $state(null);
    zarrArrayIndex: number = 0;
    dateInserted: string = '';
    dateModified: string | null = null;
    inactive: boolean = false;

    constructor(item: ServerSegmentation) {
        super();
        this.init(item);
    }

    init(serverItem: ServerSegmentation) {
        this.instanceId = serverItem.ImageInstanceID;
        this.featureId = serverItem.FeatureID;
        this.creatorId = serverItem.CreatorID;
        this.dataType = serverItem.DataType;
        this.dataRepresentation = serverItem.DataRepresentation;
        this.threshold = serverItem.Threshold;
        this.referenceId = serverItem.ReferenceSegmentationID;
        this.id = serverItem.SegmentationID;
        this.depth = serverItem.Depth;
        this.height = serverItem.Height;
        this.width = serverItem.Width;
        this.sparseAxis = serverItem.SparseAxis;
        this.imageProjectionMatrix = serverItem.ImageProjectionMatrix;
        this.scanIndices = serverItem.ScanIndices?.sort();
        this.zarrArrayIndex = serverItem.ZarrArrayIndex;
        this.dateInserted = serverItem.DateInserted;
        this.dateModified = serverItem.DateModified;
        this.inactive = serverItem.Inactive;
    }

    static async createFrom(
        image: AbstractImage,
        feature: Feature,
        creator: Creator,
        dataRepresentation: DataRepresentation,
        dataType: Datatype,
        threshold?: number,
        sparseAxis?: number,
    ) {

        const instance = image.instance;
        const scanIndices = image.is3D ? [] : null;
        let shape = {
            depth: image.depth,
            height: image.height,
            width: image.width,
        }
        if (sparseAxis == 1) {
            // projection
            shape.depth = image.height;
            shape.height = 1;
            shape.width = image.width;
        }

        const item = {
            instanceId: instance.id,
            ...shape,
            sparseAxis,
            imageProjectionMatrix: null,
            scanIndices,
            dataRepresentation,
            dataType,
            threshold,
            referenceId: null,
            creatorId: creator.id,
            featureId: feature.id,
        };

        return await Segmentation.create(item);
    }

    static async create(item: any, np_array?: NPYArray): Promise<Segmentation> {
        const formData = new FormData();
        const serverParams = toServer(item, Segmentation.mapping);

        formData.append('metadata', JSON.stringify(serverParams));

        if (np_array) {
            formData.append('np_array', await np_array.toBlob(true), 'np_array.npy.gz');
        }

        const response = await fetch(`${apiUrl}/${Segmentation.endpoint}`, {
            method: 'POST',
            body: formData,
        });
        const segmentation = await response.json();
        const imported = importData({ [Segmentation.endpoint]: [segmentation] });

        return imported[Segmentation.endpoint][0] as Segmentation;
    }

    get creator(): Creator {
        return data.creators.get(this.creatorId)!;
    }

    get feature(): Feature {
        return data.features.get(this.featureId)!;
    }

    get instance(): Instance {
        return data.instances.get(this.instanceId)!;
    }

    get study(): Study {
        return this.instance.study;
    }

    get reference(): Segmentation | undefined {
        return this.referenceId ? data.segmentations.get(this.referenceId) : undefined;
    }

    get compositeFeatures(): FilterList<CompositeFeature> {
        return data.compositeFeatures.filter(f => f.parentFeatureId == this.featureId).sort((a, b) => a.featureIndex - b.featureIndex);
    }

    async updateData(scanNr: number | null, data: ArrayBuffer) {
        // Build the query string
        const params = new URLSearchParams();
        params.append('axis', (this.sparseAxis ?? 0).toString());
        if (scanNr != null) {
            params.append('scan_nr', scanNr.toString());
        }
        const url = `${apiUrl}/${Segmentation.endpoint}/${this.id}/data?${params.toString()}`;

        const response = await fetch(url, {
            method: 'PUT',
            body: data,
            headers: {
                'Content-Type': 'application/octet-stream',
            },
        });
        const updatedSegmentation = await response.json();
        this.updateFields(updatedSegmentation);
    }

    async loadData(scanNr: number): Promise<NPYArray> {
        const params = new URLSearchParams();
        params.append('axis', (this.sparseAxis ?? 0).toString());
        params.append('scan_nr', scanNr.toString());
        const url = `${apiUrl}/${Segmentation.endpoint}/${this.id}/data?${params.toString()}`;
        const response = await fetch(url);
        return decodeNpy(await response.arrayBuffer());
    }
}
registerConstructor('segmentations', Segmentation);