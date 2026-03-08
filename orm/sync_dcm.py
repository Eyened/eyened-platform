import os
import sys
# Import database model classes
from eyened_orm import (
    Project, Patient, Study, Series, Image,
    ImageInstance, Modality, Annotation, Feature, Creator, AnnotationType,
    DeviceModel, DeviceInstance,
    Task, TaskState, TaskDefinition, SubTask,
    ModalityTable)
from eyened_orm.importer.importer import Importer
from eyened_orm.utils.config import load_config
from eyened_orm.db import Database

import cv2
from datetime import date, datetime
import json
from glob import glob
import numpy as np
import pandas as pd
from pathlib import Path
import re
import shutil
import subprocess
from tqdm import tqdm
import typer


import process_dcm


modality_map = {
    'SLO - Infrared': 'InfraredReflectance',
    'OCT': 'OCT',
    'AF - Blue': 'Autofluorescence'
}


app = typer.Typer()


@app.command()
def main(
    project_name: str = typer.Option(..., help='Project name'),
    dry_run: bool = typer.Option(False, help='Run the command without making changes'),
    verbose: bool = typer.Option(False, help='Enable verbose mode')
):
    config = load_config(os.environ)
    project_codename = project_name.replace(' ', '_')

    # 1. get all dcms
    dcm_paths = sorted(glob(f'/images/{project_codename}/**/*.dcm', recursive=True))
    print(len(dcm_paths))
    assert len(dcm_paths) > 0, f'no DCMs are found (/images/{project_codename})'

    # 2. parse and import
    import_dcms(project_name, dcm_paths, config, dry_run, verbose)


def import_dcms(project_name, dcm_paths, config, dry_run, verbose):
    with Database().get_session() as session:
        for dcm_path in tqdm(dcm_paths):
            if not os.path.exists(dcm_path):
                continue
            import_dcm(project_name, dcm_path, session, config, dry_run, verbose)


def import_dcm(project_name, dcm_path, session, config, dry_run, verbose):
    metadata = retrieve_metadata(project_name, dcm_path)
    verbose and print(metadata)

    device_model = get_device_model(metadata['manufacturer'], metadata['manufacturer_model_name'], session, dry_run)
    assert device_model is not None, f'Expect a valid device model for {metadata["manufacturer"]}::{metadata["manufacturer_model_name"]}'
    device_instance = get_device_instance(device_model, session, dry_run)
    assert device_instance is not None, f'Expect a valid default device instance for {device_model}'

    dataset_identifier = dcm_path.replace('/images/', '')
    image_instances = ImageInstance.by_columns(session, DatasetIdentifier=dataset_identifier)
    if len(image_instances) > 0:
        # update metadata
        verbose and print('\tupdating ...')
        assert len(image_instances) == 1
        update_existing_dcm(session, device_instance, metadata, image_instances[0], dry_run)
    else: # == 0
        verbose and print('\tinserting ...')
        if not dry_run:
            image_instance = import_new_dcm(session, project_name, dataset_identifier, device_instance, metadata, config)
            update_existing_dcm(session, device_instance, metadata, image_instance, dry_run)


def get_device_model(manufacturer, manufacturer_model_name, session, dry_run):
    device_models = DeviceModel.by_columns(
        session,
        Manufacturer=manufacturer,
        ManufacturerModelName=manufacturer_model_name,
    )
    if len(device_models) > 0:
        assert len(device_models) == 1
        device_model = device_models[0]
    else: # == 0
        device_model = DeviceModel(
            Manufacturer=manufacturer,
            ManufacturerModelName=manufacturer_model_name,
        )
        if not dry_run:
            session.add(device_model)
            session.commit()
    return device_model


def get_device_instance(device_model, session, dry_run):
    device_instances = DeviceInstance.by_columns(
        session,
        DeviceModelID=device_model.DeviceModelID,
        Description='Default',
    )
    if len(device_instances) > 0:
        assert len(device_instances) == 1
        device_instance = device_instances[0]
    else: # == 0
        device_instance = DeviceInstance(
            DeviceModel=device_model,
            Description='Default',
        )
        if not dry_run:
            session.add(device_instance)
            session.commit()
    return device_instance


def import_new_dcm(session, project_name, dataset_identifier, device_instance, metadata, config):
    modality = ModalityTable.by_tag(metadata['modality'], session)
    assert modality is not None
    
    record = {
        'project_name': project_name,
        'patient_identifier': metadata['patient_identifier'],
        'studies': [{
            'study_date': metadata['study_date'].date().isoformat(),
            'series': [{
                'images': [{
                    'image': dataset_identifier,
                    'props': {
                        'Laterality': str(metadata['laterality']),
                        'SourceInfoID': 1, # 'Default'
                        'DeviceInstanceID': device_instance.DeviceInstanceID, # 'Default'
                        'ModalityID': modality.ModalityID,
                        'Modality': str(metadata['modality']),
                        'SOPInstanceUid': str(metadata['sop_instance_uid']),
                        'SOPClassUid': str(metadata['sop_class_uid']),
                        'NrOfFrames': metadata['num_frames'],
                        'Columns_x': metadata['size_width'],
                        'Rows_y': metadata['size_height'],
                        'ResolutionHorizontal': metadata['resolutions_mm_width'],
                        'ResolutionVertical': metadata['resolutions_mm_height'],
                        **({'ResolutionAxial': metadata['resolutions_mm_depth']} if 'resolutions_mm_depth' in metadata else {}),
                        **({'HorizontalFieldOfView': metadata['field_of_view']} if 'field_of_view' in metadata else {}),
                        **({'SliceThickness': metadata['dimensions_mm_depth'] / metadata['num_frames']} if 'dimensions_mm_depth' in metadata else {}),
                    },
                }],
            }],
        }],
    }
    importer = Importer(
        session=session,
        create_patients=True,
        create_studies=True,
        create_series=True,
        create_projects=True,
        # run_ai_models=True,
        run_ai_models=False,
        generate_thumbnails=True,
        config=config,
    )
    importer.import_many([record])

    image_instances = ImageInstance.by_columns(session, DatasetIdentifier=dataset_identifier)
    assert len(image_instances) == 1
    return image_instances[0]


def update_existing_dcm(session, device_instance, metadata, image_instance, dry_run):
    modality = ModalityTable.by_tag(metadata['modality'], session)
    assert modality is not None

    # image_instance.Study.StudyDate = metadata['study_date'].date().isoformat()
    image_instance.Patient.BirthDate = metadata['date_of_birth'].date().isoformat()
    image_instance.Patient.Sex = metadata['gender']
    image_instance.Laterality = metadata['laterality']
    image_instance.DeviceInstance = device_instance
    image_instance.ModalityID = modality.ModalityID
    image_instance.Modality = metadata['modality']
    image_instance.SOPInstanceUid = metadata['sop_instance_uid']
    image_instance.SOPClassUid = metadata['sop_class_uid']
    image_instance.NrOfFrames = metadata['num_frames']
    image_instance.Columns_x = metadata['size_width']
    image_instance.Rows_y = metadata['size_height']
    image_instance.ResolutionHorizontal = metadata['resolutions_mm_width']
    image_instance.ResolutionVertical = metadata['resolutions_mm_height']
    if 'resolutions_mm_depth' in metadata:
        image_instance.ResolutionAxial = metadata['resolutions_mm_depth']
    if 'field_of_view' in metadata:
        image_instance.HorizontalFieldOfView = metadata['field_of_view']
    if 'dimensions_mm_depth' in metadata:
        image_instance.SliceThickness = metadata['dimensions_mm_depth'] / metadata['num_frames']
    if not dry_run:
        session.commit()


def retrieve_metadata(project_name, filepath):
    for p in glob("/tmp/*.png"):
        os.remove(p)
    for p in glob("/tmp/*.json"):
        os.remove(p)

    subprocess.run([
        'process-dcm',
        '-o', '/tmp/exported/',
        '-k', 'pDg',
        '-p',
        filepath,
    ])
    print(filepath)
    with open(f'/tmp/metadata.json', 'r') as f:
        jobj = json.load(f)
        # print(jobj)
        j_images = jobj['images']['images']

        # -- mistaken data handling
        date_of_birth = jobj['patient']['date_of_birth']

        metadata = {
            'patient_identifier': '-'.join([project_name.lower(), jobj['patient']['patient_key']]),
            'date_of_birth': datetime.strptime(date_of_birth, '%Y-%m-%d'),
            'gender': jobj['patient']['gender'],
            'study_date': datetime.strptime(jobj['exam']['scan_datetime'], '%Y-%m-%d %H:%M:%S'),
            'laterality': jobj['series']['laterality'],
            'num_frames': 1,
            'manufacturer': jobj['exam']['manufacturer'],
            'manufacturer_model_name': jobj['exam']['scanner_model'],
        }
        assert len(j_images) == 1
        j_image = j_images[0]
        metadata = {
            **metadata,
            'modality': modality_map[j_image['modality']],
            'num_frames': len(j_image['contents']),
            'sop_instance_uid': j_image['sop_instance_uid'],
            'sop_class_uid': j_image['sop_class_uid'],
            'size_width': j_image['size']['width'],
            'size_height': j_image['size']['height'],
            'resolutions_mm_width': j_image['resolutions_mm']['width'],
            'resolutions_mm_height': j_image['resolutions_mm']['height'],
        }
        if 'depth' in j_image['dimensions_mm']:
            metadata['dimensions_mm_depth'] = j_image['dimensions_mm']['depth']
        if 'depth' in j_image['resolutions_mm']:
            metadata['resolutions_mm_depth'] = j_image['resolutions_mm']['depth']
        if 'field_of_view' in j_image and j_image['field_of_view'] is not None:
            metadata['field_of_view'] = j_image['field_of_view']
        return metadata


if 'main' in __name__:
    app()
