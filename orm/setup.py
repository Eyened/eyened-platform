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
        "pydicom==3.*"
    ],
    python_requires=">=3.8",
)
