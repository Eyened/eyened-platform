# eyened-platform

A modern web platform for visualization and annotation of ophthalmic images with features like:

- Loading of various image formats including DICOM.
- Convenient system for browsing loaded studies and images.
- Task system for managing grading tasks.
- Drawing tools for 2D image segmentation of enface images and OCT B-scans
- Images and annotations are rendered in the browser, making it very responsive and easy to set up.
- Image enhancements such as contrast enhancement and CLAHE can be applied on the fly.
- Integrated tools for registration of enface images.
- Automated ETDRS grid placement via AI-based bounds detection and landmark detection (fovea, optic disc) upon insertion of CFI images.
- Python-based import script for loading images and associated metadata.
- For advanced use cases, our ORM allows data scientists to more easily work with the database.


See our [Documentation](https://eyened.github.io/eyened-platform/).

## Repository overview

***client:*** SvelteKit-based frontend application with DICOM image viewing capabilities using Cornerstone.js. Features include image annotation tools, drawing tools for 2D segmentation, and real-time image enhancements.

***dev:*** Development environment setup with Docker Compose configuration, environment variables, and scripts for starting development servers. Includes database mirroring tools and migration management.

***docker:*** Production Docker configuration with multi-stage builds for server, worker, and fileserver components. Includes nginx configuration and deployment scripts.

***docs:*** Astro-based documentation. Contains project documentation, API references, and user guides.

***orm:*** SQLAlchemy-based Object-Relational Mapping library for database interactions. Includes migration management with Alembic, data models, and utilities for data scientists to work with the database.

***server:*** FastAPI-based backend server providing REST API endpoints for image management, user authentication, task management, and database operations.