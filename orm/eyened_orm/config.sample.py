import datetime

config = {
    "database": {
        "user": "USERNAME",
        "password": "PASSWORD",
        "host": "DB_HOST", 
        "database": "DB_NAME",
        "port": "PORT",
        "raise_on_warnings": True,
    },
    "default_date": datetime.date(1970, 1, 1),  # default date for new studies
    "images_basepath": "/PATH/TO/IMAGES",
    "importer_default_path": "/PATH/TO/IMAGES/SUBFOLDER",  # default path for the importer to copy images to. Must be descendant of images_basepath
    "annotations_path": "/PATH/TO/ANNOTATIONS",
    "trash_path": "/PATH/TO/TRASH", # for deleted annotations / form_annotations
    "thumbnails_path": "/PATH/TO/THUMBNAILS",
    "image_server_url": "http://url/to/fileserver",
    "cfi_cache_path": "/PATH/TO/CFI_CACHE",
    "viewer_url": "http://url/to/viewer",
    "secret_key": "SECRET_KEY",  # key used to generate file hashes deterministically
}
