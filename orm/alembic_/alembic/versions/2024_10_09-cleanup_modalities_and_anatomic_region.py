"""Cleanup modalities and anatomic region artificial

Revision ID: 3b53d030fb6a
Revises: a7c0a9667796
Create Date: 2024-10-09 13:20:42.994122

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3b53d030fb6a"
down_revision = "a7c0a9667796"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column ETDRSField
    op.add_column(
        "ImageInstance",
        sa.Column(
            "ETDRSField",
            sa.Enum("F1", "F2", "F3", "F4", "F5", "F6", "F7", name="etdrsfield"),
            nullable=True,
        ),
    )

    ###############################
    #### Addition Modality ENUM ###
    ###############################
    op.alter_column(
        "ImageInstance",
        "Modality",
        existing_type=sa.Enum("OP", "OPT", "SC"),
        new_column_name="DICOMModality",
    )
    op.add_column(
        "ImageInstance",
        sa.Column(
            "Modality",
            sa.Enum(
                "AdaptiveOptics",
                "ColorFundus",
                "ColorFundusStereo",
                "RedFreeFundus",
                "ExternalEye",
                "LensPhotograph",
                "Ophthalmoscope",
                "Autofluorescence",
                "FluoresceinAngiography",
                "ICGA",
                "InfraredReflectance",
                "BlueReflectance",
                "GreenReflectance",
                "OCT",
                "OCTA",
            ),
            nullable=True,
        ),
    )

    # 36    Adaptive Optics             > AdaptiveOptics
    op.execute(
        "UPDATE ImageInstance SET Modality = 'AdaptiveOptics' WHERE ModalityID = 36"
    )
    # 13	Autofluorescence            > Autofluorescence
    op.execute(
        "UPDATE ImageInstance SET Modality = 'Autofluorescence' WHERE ModalityID = 13"
    )
    # 4	    Color Fundus                > ColorFundus
    op.execute("UPDATE ImageInstance SET Modality = 'ColorFundus' WHERE ModalityID = 4")
    # 9	    Color Fundus Other          > NULL - only 324 images including normal fundus, stereo and lens images
    op.execute("UPDATE ImageInstance SET Modality = NULL WHERE ModalityID = 9")
    # 16	Fluorescein                 > NULL - only 50 images, look very bad
    op.execute("UPDATE ImageInstance SET Modality = NULL WHERE ModalityID = 16")
    # 23	Fluorescein Angiography     > FluoresceinAngiography
    op.execute(
        "UPDATE ImageInstance SET Modality = 'FluoresceinAngiography' WHERE ModalityID = 23"
    )
    # 20	Infrared                    > InfraredReflectance
    op.execute(
        "UPDATE ImageInstance SET Modality = 'InfraredReflectance' WHERE ModalityID = 20"
    )
    # 40	Infrared: ReflectanceBlue   > BlueReflectance
    op.execute(
        "UPDATE ImageInstance SET Modality = 'BlueReflectance' WHERE ModalityID = 40"
    )
    # 21	Infrared: ReflectanceGreen  > GreenReflectance
    op.execute(
        "UPDATE ImageInstance SET Modality = 'GreenReflectance' WHERE ModalityID = 21"
    )
    # 6	    JSON Coordinates            > JSONCoordinates - can probably remove, but will ask Jeroen
    # 7	    Lens                        > LensPhotograph
    op.execute(
        "UPDATE ImageInstance SET Modality = 'LensPhotograph' WHERE ModalityID = 7"
    )
    # 10	Lens Other                  > ColorFundusStereo - but there are some monochrome images. Do we want to separate them?
    op.execute(
        "UPDATE ImageInstance SET Modality = 'ColorFundusStereo' WHERE ModalityID = 10"
    )
    # 5	    OCT                         > OCT
    op.execute("UPDATE ImageInstance SET Modality = 'OCT' WHERE ModalityID = 5")
    # 17	OCT B-scan                  > NULL - only 13 images
    op.execute("UPDATE ImageInstance SET Modality = NULL WHERE ModalityID = 17")
    # 12	OCT Other                   > NULL - looks like rubbish coming from the OCT machines
    op.execute("UPDATE ImageInstance SET Modality = NULL WHERE ModalityID = 12")
    # 14	Other                       > NULL - also rubbish - screen captures from an interface
    op.execute("UPDATE ImageInstance SET Modality = NULL WHERE ModalityID = 14")
    # 15	Red-free                    > RedFreeFundus
    op.execute(
        "UPDATE ImageInstance SET Modality = 'RedFreeFundus' WHERE ModalityID = 15"
    )

    # Update ImageInstance for 'External Eye Photograph'
    op.execute("""
        UPDATE ImageInstance 
        SET ModalityID = (SELECT ModalityID FROM Modality WHERE ModalityTag='External Eye Photograph') 
        WHERE AnatomicRegionArtificial = 'External'
    """)

    # Update ImageInstance for 'Color Fundus Stereo'
    op.execute("""
        UPDATE ImageInstance 
        SET ModalityID = (SELECT ModalityID FROM Modality WHERE ModalityTag='Color Fundus Stereo') 
        WHERE AnatomicRegionArtificial = 'MaculaStereo'
    """)
    op.execute(
        "UPDATE ImageInstance SET ETDRSField = 'F2' WHERE AnatomicRegionArtificial = 'MaculaStereo'"
    )

    # Update ImageInstance for 'Lens'
    op.execute("""
        UPDATE ImageInstance 
        SET ModalityID = (SELECT ModalityID FROM Modality WHERE ModalityTag='Lens') 
        WHERE AnatomicRegionArtificial = 'Lens'
    """)

    # Update ImageInstance for 'Ophthalmoscope' (Neitz)
    op.execute("""
        UPDATE ImageInstance 
        SET ModalityID = (SELECT ModalityID FROM Modality WHERE ModalityTag='Ophthalmoscope') 
        WHERE AnatomicRegionArtificial = 'Neitz'
    """)

    # Map AnatomicRegionArtificial == 'External','MaculaStereo','Lens','Neitz' to modality enum values
    op.execute(
        "UPDATE ImageInstance SET Modality = 'ExternalEye' WHERE AnatomicRegionArtificial = 'External'"
    )
    op.execute(
        "UPDATE ImageInstance SET Modality = 'ColorFundusStereo' WHERE AnatomicRegionArtificial = 'MaculaStereo'"
    )
    op.execute(
        "UPDATE ImageInstance SET Modality = 'LensPhotograph' WHERE AnatomicRegionArtificial = 'Lens'"
    )
    op.execute(
        "UPDATE ImageInstance SET Modality = 'Ophthalmoscope' WHERE AnatomicRegionArtificial = 'Neitz'"
    )

    # Update ETDRSField for 'Disc' and 'Macula'
    op.execute(
        "UPDATE ImageInstance SET ETDRSField = 'F1' WHERE AnatomicRegionArtificial = 'Disc'"
    )
    op.execute(
        "UPDATE ImageInstance SET ETDRSField = 'F2' WHERE AnatomicRegionArtificial = 'Macula'"
    )

    # TODO: Move this to quality ?
    # Set ETDRSField to NULL for 'Other', 'Unknown', and 'Ungradable'
    op.execute(
        "UPDATE ImageInstance SET ETDRSField = NULL WHERE AnatomicRegionArtificial = 'Other'"
    )
    op.execute(
        "UPDATE ImageInstance SET ETDRSField = NULL WHERE AnatomicRegionArtificial = 'Unknown'"
    )
    op.execute(
        "UPDATE ImageInstance SET ETDRSField = NULL WHERE AnatomicRegionArtificial = 'Ungradable'"
    )
    op.execute("ALTER TABLE ImageInstance DROP COLUMN AnatomicRegionArtificial")
