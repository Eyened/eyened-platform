from eyened_orm import (
    AttributesModel,
    AttributeDefinition,
    AttributeDataType,
    AttributeValue,
    ImageInstance,
)

from typing import List, Optional


class CFIROI:

    def __init__(self, session, cfi_cache_path: Optional[str] = None):
        self.session = session
        self.cfi_cache_path = cfi_cache_path
        self.model = AttributesModel.get_or_create(
            session,
            match_by={"ModelName": "CFI_ROI", "Version": "1.0"},
            create_kwargs={
                "Description": "https://github.com/Eyened/retinalysis-fundusprep"
            },
        )
        self.attr_definition = AttributeDefinition.get_or_create(
            session,
            match_by={
                "AttributeName": "CFI_ROI",
                "AttributeDataType": AttributeDataType.JSON,
            },
        )

    def run(self, image_ids: List[int]):

        from rtnls_fundusprep.preprocessor import parallel_preprocess
        from rtnls_fundusprep.cfi_bounds import CFIBounds

        images = ImageInstance.by_ids(self.session, image_ids)

        # ids and paths need to be lists for the dataloader (corresponding indices)
        ids = list(images.keys())
        paths = [image.path for image in images.values()]

        rgb_path = None
        ce_path = None
        if self.cfi_cache_path is not None:
            rgb_path = f"{self.cfi_cache_path}/rgb"
            ce_path = f"{self.cfi_cache_path}/ce"

        bounds = parallel_preprocess(
            paths,  # List of image files
            ids,
            rgb_path=rgb_path,  # Output path for RGB images
            ce_path=ce_path,  # Output path for Contrast Enhanced images
            n_jobs=8,  # number of preprocessing workers
        )
        for item in bounds:
            if not item["success"]:
                print(f"Image {item['id']} failed to preprocess")
                continue
            bounds = item["bounds"]
            bounds_dict = CFIBounds(**bounds).to_dict_all()
            if "hw" in bounds_dict:
                del bounds_dict["hw"]

            AttributeValue.upsert(
                self.session,
                match_by={
                    "AttributeID": self.attr_definition.AttributeID,
                    "ModelID": self.model.ModelID,
                    "ImageInstanceID": item["id"],
                },
                update_values={"ValueJSON": bounds_dict},
            )
