from setuptools import find_packages, setup

setup(
    name="eyened_orm",
    # using versioneer for versioning using git tags
    # https://github.com/python-versioneer/python-versioneer/blob/master/INSTALL.md
    version="0.0.1",
    author="Eyened",
    author_email="eyened@eyened.eyened",
    description="ORM for eyened tools",
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "eyened_orm": ["environments/*.env"],
    },
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "eorm = eyened_orm.cli:eorm",
        ]
    },
    install_requires=[
        "click==8.*",
        "numpy==2.*",
        "pandas==2.*",
        "matplotlib==3.*",
        "opencv-python-headless==4.*",
        "sqlalchemy==2.*",
        "jsonschema==4.*",
        "tqdm==4.*",
        "alembic==1.13.2",        
        "PyMySQL==1.0.2",
        "mysql-connector-python==8.*",
        "pydicom==3.*",
        "GPUtil==1.*",
        "requests==2.*",
        "pydantic-settings==2.7.1",
        "sqlmodel==0.0.24",
        "retinalysis-fundusprep==0.4.0",
        "zarr==3.1.0",
        "pyyaml==6.*",
    ],
    python_requires=">=3.10",
)
