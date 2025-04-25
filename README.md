# eyened-platform

A modern web platform for visualization and annotation of ophthalmic images with features like:

- Loading of various image formats including DICOM.
- Convenient system for browsing loaded studies and images.
- Task system for managing grading tasks.
- Drawing tools for 2D image segmentation of enface images and OCT B-scans
- Images and annotations are rendered in the browser, making it very responsive and easy to set up.
- Image enhancements such as CLAHE can be applied on the fly.
- Integrated tools for registration of enface images.
- Automated ETDRS grid placement via AI-based bounds detection and landmark detection (fovea, optic disc) upon insertion of - CFI images.
- Python-based import script for loading images and associated metadata.
- Authentication system can secure the viewer, images, thumbnails and annotations.
- For advanced use cases, our ORM allows data scientists to more easily work with the database.


See our [Documentation](https://eyened.github.io/eyened-platform/).

## Development setup

Our development setup will run hot-reloading development servers for the api and frontend. To avoid exposing image files, it also requires a reverse proxy nginx server set up. A [docker-compose] is provided for this server.

### Setup

0. [Install npm and node](https://nodejs.org/en/download), required for the frontend.

1. Create an environment, clone the repo, and install Python and Node dependencies:
    ```
    conda create --name viewer python=3.11
    git clone https://github.com/Eyened/eyened-platform.git eyened_platform
    cd eyened_platform/server
    pip install -r requirements.txt
    cd ../client
    npm install
    ```


2. Copy `sample.dev.env` into `dev.env` and configure the variables documented in it.

### Regular usage

- Keep the development nginx docker running
- When working on eyened platform run:
    ```
    ./start_client_dev.sh
    ```
    and:
    ```
    ./start_server_dev.sh
    ```
    on separate terminals.
