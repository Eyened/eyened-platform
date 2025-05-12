import os

import numpy as np
import pydicom
from PIL import Image

from eyened_orm.ImageInstance import ImageInstance
from eyened_orm.reports import Report


# Read relevant database fields from ImageInstance to create the report
# The original instance is then no longer needed, so this object can be used in multiprocessing pool
class InstanceReport:
    def __init__(self, instance: ImageInstance):
        self.image_id = instance.ImageInstanceID
        self.path = instance.path
        self.etdrs = instance.ETDRS_masks()
        self.h = instance.Rows_y
        self.w = instance.Columns_x

    def load_image(self):
        if self.path.endswith(".dcm"):
            ds = pydicom.dcmread(self.path)
            return ds.pixel_array
        else:
            return np.array(Image.open(self.path))

    def create_report(self, feature_images):
        return Report(feature_images, self.etdrs, self.etdrs.all_fields)

    def export_report(self, report, results_folder):
        output_folder = f"{results_folder}/{self.image_id}"
        os.makedirs(output_folder, exist_ok=True)
        image = self.load_image()
        report.export(output_folder, image, self.image_id)
