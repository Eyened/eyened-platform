import type { Annotation } from './annotation';
import type { Device } from './device';
import { DerivedProperty, ItemConstructor, PropertyChain } from './itemContructor';
import type { FilterList, Item } from './itemList';
import { FKMapping } from './mapping';
import { data, type DataModel } from './model';
import type { Patient } from './patient';
import type { Project } from './project';
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
export type AnatomicRegion = '1' | '2' | 'External' | '1-Stereo' | 'Lens' | 'Neitz' | 'Other' | 'Unknown' | 'Ungradable' | null;
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

export interface Instance extends Item {
    id: number,
    series: Series,
    study: Study,
    patient: Patient,
    project: Project,
    sourceID: string,
    device: Device,
    SOPInstanceUid: string,
    datasetIdentifier: string,
    thumbnailIdentifier: string,
    laterality: Laterality,
    modality: string,
    dicomModality: string,
    etdrsField: string,
    angioGraphy: string,
    scan: Scan,
    anatomicRegion: AnatomicRegion,
    anatomicRegionArtificial: string,
    rows: number,
    columns: number,
    nrOfFrames: number,
    resolutionHorizontal: number,
    resolutionVertical: number,
    resolutionAxial: number,
    cfROI?: ROI,
    cfKeypoints?: Keypoints,
    cfQuality?: number,
    inactive: number,

    annotations: FilterList<Annotation>
}

export const InstanceConstructor = new ItemConstructor<Instance>('ImageInstanceID', {
    series: FKMapping('SeriesID', 'series'),
    study: PropertyChain(['series', 'study']),
    patient: PropertyChain(['series', 'study', 'patient']),
    project: PropertyChain(['series', 'study', 'patient', 'project']),
    sourceID: 'SourceInfoID',
    device: FKMapping('DeviceInstanceID', 'devices'),
    modality: 'Modality',
    scan: FKMapping('ScanID', 'scans'),
    SOPInstanceUid: 'SOPInstanceUid',
    datasetIdentifier: 'DatasetIdentifier',
    thumbnailIdentifier: 'ThumbnailIdentifier',
    // manufacturer: 'Manufacturer',
    // manufacturerModelName: 'ManufacturerModelName',
    laterality: 'Laterality',
    dicomModality: 'DICOMModality',
    etdrsField: 'ETDRSField',
    angioGraphy: 'Angiography',
    anatomicRegion: 'AnatomicRegion',
    // anatomicRegionArtificial: 'AnatomicRegionArtificial',
    rows: 'Rows_y',
    columns: 'Columns_x',
    nrOfFrames: 'NrOfFrames',

    resolutionHorizontal: 'ResolutionHorizontal',
    resolutionVertical: 'ResolutionVertical',
    resolutionAxial: 'ResolutionAxial',
    cfROI: 'CFROI',
    cfKeypoints: 'CFKeypoints',
    cfQuality: 'CFQuality',
    inactive: 'Inactive',

    annotations: new DerivedProperty((self: Instance, data: DataModel) => data.annotations.filter(annotation => annotation.instance == self)),
});

export function getInstanceByDataSetIdentifier(datasetIdentifier: string): Instance | undefined {
    return data.instances.find(instance => instance.datasetIdentifier == datasetIdentifier);
}

export function getInstanceBySOPInstanceUID(SOPInstanceUid: string): Instance | undefined {
    return data.instances.find(instance => instance.SOPInstanceUid == SOPInstanceUid);
}