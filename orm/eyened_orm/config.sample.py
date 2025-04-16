import datetime

config = {
    # ---- MySQL Database configuration
    "database": {
        "user": "USERNAME",
        "password": "PASSWORD",
        "host": "DB_HOST",
        "database": "DB_NAME",
        "port": "PORT",
        "raise_on_warnings": True,
    },
    # ---- Basic configuration
    # annotations_path(required): path to the folder containing annotations
    # used by the platform for reading and writing annotations
    "annotations_path": "/PATH/TO/ANNOTATIONS",

    # thumbnails_path(required): folder containing the thumbnail structure
    # used by the ORM to read thumbnails
    # use by the importer to write thumbnails on insertion
    "thumbnails_path": "/PATH/TO/THUMBNAILS",
    
    # ---- Configuration for the importer
    # images_basepath (required): The folder containing local image data.
    # All local images linked in the eyened database should be stored in this folder (or descendants)
    # File references in the database will be relative to this folder.
    # this folder should be served if used with the eyened-viewer
    "images_basepath": "/PATH/TO/IMAGES",

    # default_date (optional): default date for new studies
    # When the importer needs to create new studies and it does not receive a study date, it will use this default date.
    # defaults to 1970-01-01
    "default_date": None, 

    # importer_copy_path (optional): folder for the importer to copy images to when ran with copy_files=True
    # only required when running the importer with the copy_files=True option
    # it should be a descendant of images_basepath
    "importer_copy_path": None,

    # cfi_cache_path (optional): path of a cache for fundus images .
    # used by the importer to write a preprocessed version of the images
    # the cache is only written if this path is set
    "cfi_cache_path": None,

    # secret_key (optional): secret key used to generate hashes deterministically for anonymisation and obfuscation of file names
    # if not set, the db_id will be used as the filename
    "secret_key": None,  

    # ---- Extra options
    # image_server_url (optional): url of the image server endpoint.
    # Used by the orm to generate urls to images as <image_server_url>/<dataset_identifier>
    "image_server_url": None,
    # trash_path (optional): folder to move deleted annotations / form_annotations to when deleted from the ORM
    # if not set, the annotations will not be moved to a trash folder
    "trash_path": None,
}
