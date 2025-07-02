import type { Annotation } from './annotation.svelte';
import type { Device, DeviceModel } from './device.svelte';
import { BaseItem, FilterList } from './itemList';
import { data } from './model';
import type { Patient } from './patient';
import type { Project } from './project.svelte';
import type { Scan } from './scan';
import type { Series } from './series';
import type { Study } from './study';

export type Keypoints = {
    fovea_xy: [number, number],
    disc_edge_xy: [number, number],
    prep_fovea_xy: [number, number],
    prep_disc_edge_xy: [number, number]
}
export type Laterality = 'L' | 'R';
export type ETDRSField = 'F1' | 'F2' | 'F3' | 'F4' | 'F5' | 'F6' | 'F7'
export type ROI = {
    center: [number, number];
    radius: number;
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    lines: {
        top?: [[number, number], [number, number]]
        bottom?: [[number, number], [number, number]]
        left?: [[number, number], [number, number]]
        right?: [[number, number], [number, number]]
    }
    w: number;
    h: number;
}
export interface ServerInstance {
    ImageInstanceID: number;
    SeriesID: number;
    DeviceInstanceID: number;
    ScanID?: number;
    DatasetIdentifier: string;
    Modality: string;
    DICOMModality: string;
    SOPInstanceUid: string;
    ETDRSField: ETDRSField;
    Angiography: number;
    AnatomicRegion: number;
    Rows_y: number;
    Columns_x: number;
    NrOfFrames: number;
    ResolutionHorizontal: number;
    ResolutionVertical: number;
    ResolutionAxial: number;
    CFROI?: ROI;
    CFKeypoints?: Keypoints;
    CFQuality?: number;
    Laterality?: Laterality;
    ThumbnailPath?: string;
}
export class Instance extends BaseItem {
    static endpoint = 'instances';
    static mapping = {
        'SeriesID': 'seriesId',
        'DeviceInstanceID': 'deviceId',
        'ScanID': 'scanId',
        'DatasetIdentifier': 'datasetIdentifier',
        'Modality': 'modality',
        'Laterality': 'laterality',
        'DICOMModality': 'dicomModality',
        'SOPInstanceUid': 'SOPInstanceUid',
        'ETDRSField': 'etdrsField',
        'Angiography': 'angiography',
        'AnatomicRegion': 'anatomicRegion',
        'Rows_y': 'rows',
        'Columns_x': 'columns',
        'NrOfFrames': 'nrOfFrames',
        'ResolutionHorizontal': 'resolutionHorizontal',
        'ResolutionVertical': 'resolutionVertical',
        'ResolutionAxial': 'resolutionAxial',
        'CFROI': 'cfROI',
        'CFKeypoints': 'cfKeypoints',
        'CFQuality': 'cfQuality',
        'ThumbnailPath': 'thumbnailPath',
    };

    id!: number;
    seriesId!: number;
    deviceId!: number;
    scanId?: number;
    datasetIdentifier!: string;
    modality!: string;
    laterality?: Laterality = $state(undefined);
    dicomModality!: string;
    SOPInstanceUid!: string;
    etdrsField!: ETDRSField;
    angiography!: number;
    anatomicRegion!: number;
    rows!: number;
    columns!: number;
    nrOfFrames!: number;
    resolutionHorizontal!: number;
    resolutionVertical!: number;
    resolutionAxial!: number;
    cfROI?: ROI;
    cfKeypoints?: Keypoints;
    cfQuality?: number;
    thumbnailPath?: string;

    constructor(item: ServerInstance) {
        super();
        this.init(item);
    }

    init(item: ServerInstance) {

        this.id = item.ImageInstanceID;
        this.seriesId = item.SeriesID;
        this.deviceId = item.DeviceInstanceID;
        this.datasetIdentifier = item.DatasetIdentifier;
        this.modality = item.Modality;
        this.dicomModality = item.DICOMModality;
        this.SOPInstanceUid = item.SOPInstanceUid;
        this.etdrsField = item.ETDRSField;
        this.angiography = item.Angiography;
        this.anatomicRegion = item.AnatomicRegion;
        this.rows = item.Rows_y;
        this.columns = item.Columns_x;
        this.nrOfFrames = item.NrOfFrames;
        this.resolutionHorizontal = item.ResolutionHorizontal;
        this.resolutionVertical = item.ResolutionVertical;
        this.resolutionAxial = item.ResolutionAxial;
        this.cfROI = item.CFROI;
        this.cfKeypoints = item.CFKeypoints;
        this.cfQuality = item.CFQuality;
        this.laterality = item.Laterality;
        this.thumbnailPath = item.ThumbnailPath;
    }

    get series(): Series {
        return data.series.get(this.seriesId)!;
    }

    get study(): Study {
        return data.studies.get(this.series.studyId)!;
    }

    get patient(): Patient {
        return data.patients.get(this.study.patientId)!;
    }

    get project(): Project {
        return data.projects.get(this.patient.projectId)!;
    }

    get device(): Device {
        return data.devices.get(this.deviceId)!;
    }

    get deviceModel(): DeviceModel {
        return data.deviceModels.get(this.device.deviceModelId)!;
    }

    get scan(): Scan | undefined {
        return this.scanId == undefined ? undefined : data.scans.get(this.scanId);
    }

    get annotations(): FilterList<Annotation> {
        return data.annotations.filter(annotation => annotation.instanceId == this.id);
    }
}

export function getInstanceByDataSetIdentifier(datasetIdentifier: string): Instance | undefined {
    return data.instances.find(instance => instance.datasetIdentifier == datasetIdentifier);
}

export function getInstanceBySOPInstanceUID(SOPInstanceUid: string): Instance | undefined {
    return data.instances.find(instance => instance.SOPInstanceUid == SOPInstanceUid);
}