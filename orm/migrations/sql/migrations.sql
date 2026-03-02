Target database: root@eyened-gpu:23308/eyened_database. Proceed? [y/N] CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 832ed384515f

INSERT INTO alembic_version (version_num) VALUES ('832ed384515f');

-- Running upgrade 832ed384515f -> e69c5e4002ed

ALTER TABLE `Contact` ADD COLUMN `Orcid` VARCHAR(255);

ALTER TABLE `Contact` MODIFY `Name` VARCHAR(255) NOT NULL;

ALTER TABLE `Contact` MODIFY `Email` VARCHAR(255) NOT NULL;

ALTER TABLE `Contact` MODIFY `Institute` VARCHAR(255) NULL;

ALTER TABLE `Creator` CHANGE `MSN` `EmployeeIdentifier` VARCHAR(255) NULL;

ALTER TABLE `Creator` ADD COLUMN `PasswordHash` VARCHAR(255);

ALTER TABLE `Feature` DROP COLUMN `Modality`;

ALTER TABLE `FormAnnotation` DROP FOREIGN KEY `fk_FormAnnotation_ImageInstance1`;

ALTER TABLE `FormAnnotation` ADD FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`);

ALTER TABLE `FormSchema` MODIFY `SchemaName` VARCHAR(255) NOT NULL;

ALTER TABLE `ImageInstance` DROP COLUMN `ThumbnailIdentifier`;

ALTER TABLE `Patient` MODIFY `PatientIdentifier` VARCHAR(255) NOT NULL;

ALTER TABLE `Project` ADD COLUMN `DOI` VARCHAR(255);

ALTER TABLE `Project` MODIFY `ProjectName` VARCHAR(255) NOT NULL;

ALTER TABLE `Series` DROP FOREIGN KEY `fk_Series_Study1`;

ALTER TABLE `Series` ADD FOREIGN KEY(`StudyID`) REFERENCES `Study` (`StudyID`);

CREATE INDEX `StudyDate_idx` ON `Study` (`StudyDate`);

ALTER TABLE `SubTask` ADD COLUMN `Comments` TEXT;

ALTER TABLE `SubTaskImageLink` DROP COLUMN `SubTaskImageLinkID`;

ALTER TABLE `TaskDefinition` ADD COLUMN `TaskConfig` JSON;

ALTER TABLE `TaskState` ADD UNIQUE (`TaskStateName`);

UPDATE alembic_version SET version_num='e69c5e4002ed' WHERE alembic_version.version_num = '832ed384515f';

-- Running upgrade e69c5e4002ed -> b5d7958b7e13

CREATE TABLE `CreatorTag` (
    `TagID` INTEGER NOT NULL, 
    `CreatorID` INTEGER NOT NULL, 
    `DateInserted` DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (`TagID`, `CreatorID`), 
    FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`) ON DELETE CASCADE, 
    FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE
);

CREATE INDEX `fk_CreatorTag_Creator1_idx` ON `CreatorTag` (`CreatorID`);

CREATE INDEX `fk_CreatorTag_Tag1_idx` ON `CreatorTag` (`TagID`);

CREATE TABLE `AnnotationTag` (
    `TagID` INTEGER NOT NULL, 
    `AnnotationID` INTEGER NOT NULL, 
    `CreatorID` INTEGER NOT NULL, 
    `DateInserted` DATETIME NOT NULL DEFAULT now(), 
    PRIMARY KEY (`TagID`, `AnnotationID`), 
    FOREIGN KEY(`AnnotationID`) REFERENCES `Annotation` (`AnnotationID`), 
    FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`), 
    FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`)
);

CREATE INDEX `fk_AnnotationTag_Annotation1_idx` ON `AnnotationTag` (`AnnotationID`);

CREATE INDEX `fk_AnnotationTag_Creator1_idx` ON `AnnotationTag` (`CreatorID`);

CREATE INDEX `fk_AnnotationTag_Tag1_idx` ON `AnnotationTag` (`TagID`);

ALTER TABLE `Annotation` ADD FOREIGN KEY(`AnnotationReferenceID`) REFERENCES `Annotation` (`AnnotationID`);

ALTER TABLE `FormAnnotationTag` ADD COLUMN `CreatorID` INTEGER NOT NULL;

ALTER TABLE `FormAnnotationTag` ADD COLUMN `DateInserted` DATETIME NOT NULL DEFAULT now();

CREATE INDEX `fk_FormAnnotationTag_Creator1_idx` ON `FormAnnotationTag` (`CreatorID`);

ALTER TABLE `FormAnnotationTag` ADD FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`);

ALTER TABLE `ImageInstanceTag` ADD COLUMN `CreatorID` INTEGER NOT NULL;

ALTER TABLE `ImageInstanceTag` ADD COLUMN `DateInserted` DATETIME NOT NULL DEFAULT now();

CREATE INDEX `fk_ImageInstanceTag_Creator1_idx` ON `ImageInstanceTag` (`CreatorID`);

ALTER TABLE `ImageInstanceTag` ADD FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`);

CREATE INDEX `fk_Project_Contact1_idx` ON `Project` (`ContactID`);

ALTER TABLE `SegmentationTag` ADD COLUMN `CreatorID` INTEGER NOT NULL;

ALTER TABLE `SegmentationTag` ADD COLUMN `DateInserted` DATETIME NOT NULL DEFAULT now();

CREATE INDEX `fk_SegmentationTag_Creator1_idx` ON `SegmentationTag` (`CreatorID`);

ALTER TABLE `SegmentationTag` ADD FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`);

ALTER TABLE `StudyTag` ADD COLUMN `CreatorID` INTEGER NOT NULL;

ALTER TABLE `StudyTag` ADD COLUMN `DateInserted` DATETIME NOT NULL DEFAULT now();

CREATE INDEX `fk_StudyTag_Creator1_idx` ON `StudyTag` (`CreatorID`);

ALTER TABLE `StudyTag` ADD FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`);

ALTER TABLE `Tag` ADD COLUMN `TagType` ENUM('Study','ImageInstance','Annotation','Segmentation','FormAnnotation') NOT NULL;

ALTER TABLE `Tag` ADD COLUMN `TagDescription` VARCHAR(256) NOT NULL;

ALTER TABLE `Tag` ADD COLUMN `CreatorID` INTEGER NOT NULL;

ALTER TABLE `Tag` ADD COLUMN `DateInserted` DATETIME NOT NULL DEFAULT now();

CREATE INDEX `fk_Tag_Creator1_idx` ON `Tag` (`CreatorID`);

ALTER TABLE `Tag` ADD FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`);

UPDATE alembic_version SET version_num='b5d7958b7e13' WHERE alembic_version.version_num = 'e69c5e4002ed';

-- Running upgrade b5d7958b7e13 -> d155d64d71b3

ALTER TABLE `SubTask` ADD COLUMN `TaskState` ENUM('NotStarted','Busy','Ready') NOT NULL;

UPDATE SubTask SET TaskState = 'NotStarted' WHERE TaskStateID = 1;

UPDATE SubTask SET TaskState = 'Busy' WHERE TaskStateID = 2;

UPDATE SubTask SET TaskState = 'Ready' WHERE TaskStateID = 3;

ALTER TABLE `CompositeFeature` DROP FOREIGN KEY `CompositeFeature_ibfk_2`;

ALTER TABLE `CompositeFeature` ADD FOREIGN KEY(`ParentFeatureID`) REFERENCES `Feature` (`FeatureID`) ON DELETE CASCADE;

ALTER TABLE `SubTask` DROP FOREIGN KEY `fk_SubTask_TaskState1`;

DROP INDEX `fk_SubTask_TaskState1_idx` ON `SubTask`;

ALTER TABLE `Task` DROP FOREIGN KEY `fk_Task_TaskState1`;

DROP INDEX `fk_Task_TaskState1_idx` ON `Task`;

ALTER TABLE `SubTask` DROP COLUMN `TaskStateID`;

DROP TABLE `TaskState`;

UPDATE alembic_version SET version_num='d155d64d71b3' WHERE alembic_version.version_num = 'b5d7958b7e13';

-- Running upgrade d155d64d71b3 -> 31212c7f33fd

ALTER TABLE `Annotation` DROP FOREIGN KEY `Annotation_ibfk_1`;

ALTER TABLE `Annotation` ADD FOREIGN KEY(`AnnotationReferenceID`) REFERENCES `Annotation` (`AnnotationID`) ON DELETE CASCADE;

ALTER TABLE `AnnotationTag` DROP FOREIGN KEY `AnnotationTag_ibfk_3`;

ALTER TABLE `AnnotationTag` DROP FOREIGN KEY `AnnotationTag_ibfk_1`;

ALTER TABLE `AnnotationTag` ADD FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE;

ALTER TABLE `AnnotationTag` ADD FOREIGN KEY(`AnnotationID`) REFERENCES `Annotation` (`AnnotationID`) ON DELETE CASCADE;

ALTER TABLE `FormAnnotation` DROP FOREIGN KEY `fk_FormAnnotation_SubTask1`;

ALTER TABLE `FormAnnotation` DROP FOREIGN KEY `FormAnnotation_ibfk_1`;

ALTER TABLE `FormAnnotation` DROP FOREIGN KEY `fk_FormAnnotation_FormAnnotation1`;

ALTER TABLE `FormAnnotation` ADD FOREIGN KEY(`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE SET NULL;

ALTER TABLE `FormAnnotation` ADD FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE;

ALTER TABLE `FormAnnotation` ADD FOREIGN KEY(`FormAnnotationReferenceID`) REFERENCES `FormAnnotation` (`FormAnnotationID`) ON DELETE CASCADE;

ALTER TABLE `FormAnnotationTag` DROP FOREIGN KEY `FormAnnotationTag_ibfk_2`;

ALTER TABLE `FormAnnotationTag` DROP FOREIGN KEY `FormAnnotationTag_ibfk_1`;

ALTER TABLE `FormAnnotationTag` ADD FOREIGN KEY(`FormAnnotationID`) REFERENCES `FormAnnotation` (`FormAnnotationID`) ON DELETE CASCADE;

ALTER TABLE `FormAnnotationTag` ADD FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE;

ALTER TABLE `ImageInstanceTag` DROP FOREIGN KEY `fk_ImageInstanceTag_Tag1`;

ALTER TABLE `ImageInstanceTag` DROP FOREIGN KEY `fk_ImageInstanceTag_ImageInstance1`;

ALTER TABLE `ImageInstanceTag` ADD FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE;

ALTER TABLE `ImageInstanceTag` ADD FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE;

ALTER TABLE `Patient` DROP FOREIGN KEY `fk_Patient_Project1`;

ALTER TABLE `Patient` ADD FOREIGN KEY(`ProjectID`) REFERENCES `Project` (`ProjectID`) ON DELETE CASCADE;

ALTER TABLE `Segmentation` DROP FOREIGN KEY `Segmentation_ibfk_5`;

ALTER TABLE `Segmentation` ADD FOREIGN KEY(`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE SET NULL;

ALTER TABLE `SegmentationTag` DROP FOREIGN KEY `SegmentationTag_ibfk_2`;

ALTER TABLE `SegmentationTag` DROP FOREIGN KEY `SegmentationTag_ibfk_1`;

ALTER TABLE `SegmentationTag` ADD FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE;

ALTER TABLE `SegmentationTag` ADD FOREIGN KEY(`SegmentationID`) REFERENCES `Segmentation` (`SegmentationID`) ON DELETE CASCADE;

ALTER TABLE `Series` DROP FOREIGN KEY `Series_ibfk_1`;

ALTER TABLE `Series` ADD FOREIGN KEY(`StudyID`) REFERENCES `Study` (`StudyID`) ON DELETE CASCADE;

ALTER TABLE `Study` DROP FOREIGN KEY `fk_Study_Patient1`;

ALTER TABLE `Study` ADD FOREIGN KEY(`PatientID`) REFERENCES `Patient` (`PatientID`) ON DELETE CASCADE;

ALTER TABLE `StudyTag` DROP FOREIGN KEY `fk_StudyTag_Study1`;

ALTER TABLE `StudyTag` DROP FOREIGN KEY `fk_StudyTag_Tag1`;

ALTER TABLE `StudyTag` ADD FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE;

ALTER TABLE `StudyTag` ADD FOREIGN KEY(`StudyID`) REFERENCES `Study` (`StudyID`) ON DELETE CASCADE;

ALTER TABLE `SubTask` DROP FOREIGN KEY `fk_SubTask_Task1`;

ALTER TABLE `SubTask` ADD FOREIGN KEY(`TaskID`) REFERENCES `Task` (`TaskID`) ON DELETE CASCADE;

ALTER TABLE `SubTaskImageLink` DROP FOREIGN KEY `fk_SubTaskImageLink_SubTask1`;

ALTER TABLE `SubTaskImageLink` DROP FOREIGN KEY `fk_SubTaskImageLink_ImageInstance1`;

ALTER TABLE `SubTaskImageLink` ADD FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE;

ALTER TABLE `SubTaskImageLink` ADD FOREIGN KEY(`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE CASCADE;

ALTER TABLE `Task` DROP COLUMN `TaskStateID`;

UPDATE alembic_version SET version_num='31212c7f33fd' WHERE alembic_version.version_num = 'd155d64d71b3';

-- Running upgrade 31212c7f33fd -> 62b55e9c9e70

ALTER TABLE `FormAnnotation` DROP FOREIGN KEY `FormAnnotation_ibfk_3`;

DROP INDEX `fk_FormAnnotation_FormAnnotation1` ON `FormAnnotation`;

CREATE INDEX `ix_FormAnnotation_FormAnnotationReferenceID` ON `FormAnnotation` (`FormAnnotationReferenceID`);

ALTER TABLE `FormAnnotation` ADD CONSTRAINT `fk_FormAnnotation_FormAnnotationReferenceID` FOREIGN KEY(`FormAnnotationReferenceID`) REFERENCES `FormAnnotation` (`FormAnnotationID`) ON DELETE CASCADE;

ALTER TABLE `FormAnnotation` ADD FOREIGN KEY(`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE SET NULL;

ALTER TABLE `Task` ADD COLUMN `CreatorID` INTEGER;

ALTER TABLE `Task` ADD COLUMN `TaskState` ENUM('NotStarted','Busy','Finished','Aborted','Archived') NOT NULL;

ALTER TABLE `Task` ADD FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`);

UPDATE alembic_version SET version_num='62b55e9c9e70' WHERE alembic_version.version_num = '31212c7f33fd';

-- Running upgrade 62b55e9c9e70 -> 60f64f6c2042

DROP INDEX `TagName_UNIQUE` ON `Tag`;

ALTER TABLE `Tag` ADD CONSTRAINT `Tag` UNIQUE (`TagName`, `TagType`);

UPDATE alembic_version SET version_num='60f64f6c2042' WHERE alembic_version.version_num = '62b55e9c9e70';

-- Running upgrade 60f64f6c2042 -> 496f91a008b7

ALTER TABLE `Model` ADD COLUMN `ModelType` ENUM('segmentation','attributes');

UPDATE Model SET ModelType = 'segmentation' WHERE ModelType IS NULL;

ALTER TABLE `Model` MODIFY `ModelType` ENUM('segmentation','attributes') NOT NULL;

CREATE TABLE `Attributes` (
    `AttributeID` INTEGER NOT NULL AUTO_INCREMENT, 
    `AttributeName` VARCHAR(255) NOT NULL, 
    `AttributeDataType` ENUM('String','Float','Int','JSON') NOT NULL, 
    `ModelID` INTEGER NOT NULL, 
    PRIMARY KEY (`AttributeID`), 
    FOREIGN KEY(`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE, 
    CONSTRAINT `uq_Attributes_ModelID_AttributeName` UNIQUE (`ModelID`, `AttributeName`)
);

CREATE INDEX `fk_Attributes_Model1_idx` ON `Attributes` (`ModelID`);

CREATE TABLE `AttributesModel` (
    `ModelID` INTEGER NOT NULL, 
    PRIMARY KEY (`ModelID`), 
    FOREIGN KEY(`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE
);

CREATE TABLE `SegmentationModel` (
    `ModelID` INTEGER NOT NULL, 
    `FeatureID` INTEGER, 
    PRIMARY KEY (`ModelID`), 
    FOREIGN KEY(`FeatureID`) REFERENCES `Feature` (`FeatureID`), 
    FOREIGN KEY(`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE
);

CREATE TABLE `ImageAttributes` (
    `ImageAttributeID` INTEGER NOT NULL AUTO_INCREMENT, 
    `ImageInstanceID` INTEGER NOT NULL, 
    `AttributeID` INTEGER NOT NULL, 
    `ValueFloat` FLOAT, 
    `ValueInt` INTEGER, 
    `ValueText` VARCHAR(255), 
    `ValueJSON` JSON, 
    PRIMARY KEY (`ImageAttributeID`), 
    FOREIGN KEY(`AttributeID`) REFERENCES `Attributes` (`AttributeID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE, 
    CONSTRAINT `uq_ImageAttributes_ImageInstanceID_AttributeID` UNIQUE (`ImageInstanceID`, `AttributeID`)
);

INSERT INTO SegmentationModel (ModelID, FeatureID)
        SELECT ModelID, FeatureID
        FROM Model;

CREATE INDEX `fk_ImageAttributes_Attribute1_idx` ON `ImageAttributes` (`AttributeID`);

CREATE INDEX `fk_ImageAttributes_ImageInstance1_idx` ON `ImageAttributes` (`ImageInstanceID`);

ALTER TABLE `Model` DROP FOREIGN KEY `Model_ibfk_1`;

ALTER TABLE `Model` DROP COLUMN `FeatureID`;

UPDATE alembic_version SET version_num='496f91a008b7' WHERE alembic_version.version_num = '60f64f6c2042';

-- Running upgrade 496f91a008b7 -> 048a18ac8486

CREATE TABLE `AttributeDefinition` (
    `AttributeID` INTEGER NOT NULL AUTO_INCREMENT, 
    `AttributeName` VARCHAR(255) NOT NULL, 
    `AttributeDataType` ENUM('String','Float','Int','JSON') NOT NULL, 
    PRIMARY KEY (`AttributeID`), 
    CONSTRAINT `uq_AttributeDefinition_AttributeName` UNIQUE (`AttributeName`)
);

CREATE TABLE `AttributesModelOutput` (
    `ModelID` INTEGER NOT NULL, 
    `AttributeID` INTEGER NOT NULL, 
    PRIMARY KEY (`ModelID`, `AttributeID`), 
    FOREIGN KEY(`AttributeID`) REFERENCES `AttributeDefinition` (`AttributeID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ModelID`) REFERENCES `AttributesModel` (`ModelID`) ON DELETE CASCADE
);

CREATE TABLE `ModelInput` (
    `ModelInputID` INTEGER NOT NULL AUTO_INCREMENT, 
    `ModelID` INTEGER NOT NULL, 
    `InputAttributeID` INTEGER NOT NULL, 
    `InputName` VARCHAR(255) NOT NULL, 
    PRIMARY KEY (`ModelInputID`), 
    FOREIGN KEY(`InputAttributeID`) REFERENCES `AttributeDefinition` (`AttributeID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ModelID`) REFERENCES `AttributesModel` (`ModelID`) ON DELETE CASCADE, 
    CONSTRAINT `uq_ModelInput_ModelID_InputAttributeID` UNIQUE (`ModelID`, `InputAttributeID`)
);

CREATE INDEX `fk_ModelInput_Attribute1_idx` ON `ModelInput` (`InputAttributeID`);

CREATE INDEX `fk_ModelInput_Model1_idx` ON `ModelInput` (`ModelID`);

CREATE TABLE `AttributeValue` (
    `AttributeValueID` INTEGER NOT NULL AUTO_INCREMENT, 
    `AttributeID` INTEGER NOT NULL, 
    `ModelID` INTEGER NOT NULL, 
    `ImageInstanceID` INTEGER, 
    `SegmentationID` INTEGER, 
    `ModelSegmentationID` INTEGER, 
    `ValueFloat` FLOAT, 
    `ValueInt` INTEGER, 
    `ValueText` VARCHAR(255), 
    `ValueJSON` JSON, 
    PRIMARY KEY (`AttributeValueID`), 
    CONSTRAINT `ck_AttributeValue_exactly_one_entity` CHECK ((ImageInstanceID IS NOT NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NULL) OR (ImageInstanceID IS NULL AND SegmentationID IS NOT NULL AND ModelSegmentationID IS NULL) OR (ImageInstanceID IS NULL AND SegmentationID IS NULL AND ModelSegmentationID IS NOT NULL)), 
    FOREIGN KEY(`AttributeID`) REFERENCES `AttributeDefinition` (`AttributeID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ModelSegmentationID`) REFERENCES `ModelSegmentation` (`ModelSegmentationID`) ON DELETE CASCADE, 
    FOREIGN KEY(`SegmentationID`) REFERENCES `Segmentation` (`SegmentationID`) ON DELETE CASCADE
);

ALTER TABLE `AttributeValue` ADD CONSTRAINT `uq_AttributeValue_image_attribute_model` UNIQUE (`ImageInstanceID`, `AttributeID`, `ModelID`);

ALTER TABLE `AttributeValue` ADD CONSTRAINT `uq_AttributeValue_modelseg_attribute_model` UNIQUE (`ModelSegmentationID`, `AttributeID`, `ModelID`);

ALTER TABLE `AttributeValue` ADD CONSTRAINT `uq_AttributeValue_segmentation_attribute_model` UNIQUE (`SegmentationID`, `AttributeID`, `ModelID`);

CREATE INDEX `fk_AttributeValue_Attribute1_idx` ON `AttributeValue` (`AttributeID`);

CREATE INDEX `fk_AttributeValue_ImageInstance1_idx` ON `AttributeValue` (`ImageInstanceID`);

CREATE INDEX `fk_AttributeValue_Model1_idx` ON `AttributeValue` (`ModelID`);

CREATE INDEX `fk_AttributeValue_ModelSegmentation1_idx` ON `AttributeValue` (`ModelSegmentationID`);

CREATE INDEX `fk_AttributeValue_Segmentation1_idx` ON `AttributeValue` (`SegmentationID`);

CREATE TABLE `AttributeValueInput` (
    `OutputAttributeValueID` INTEGER NOT NULL, 
    `InputAttributeValueID` INTEGER NOT NULL, 
    PRIMARY KEY (`OutputAttributeValueID`, `InputAttributeValueID`), 
    FOREIGN KEY(`InputAttributeValueID`) REFERENCES `AttributeValue` (`AttributeValueID`) ON DELETE CASCADE, 
    FOREIGN KEY(`OutputAttributeValueID`) REFERENCES `AttributeValue` (`AttributeValueID`) ON DELETE CASCADE
);

DROP TABLE `ImageAttributes`;

DROP TABLE `Attributes`;

UPDATE alembic_version SET version_num='048a18ac8486' WHERE alembic_version.version_num = '496f91a008b7';

-- Running upgrade 048a18ac8486 -> ccb5ba8245c7

ALTER TABLE `Annotation` ALTER COLUMN `Inactive` DROP DEFAULT;

ALTER TABLE `Annotation` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `AnnotationData` ALTER COLUMN `DateModified` DROP DEFAULT;

ALTER TABLE `AnnotationTag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Creator` ALTER COLUMN `IsHuman` DROP DEFAULT;

ALTER TABLE `Creator` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `CreatorTag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Feature` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `FormAnnotation` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `FormAnnotation` CHANGE `DateModified` `DateModified` DATETIME NULL DEFAULT now();

ALTER TABLE `FormAnnotationTag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `ImageInstance` ALTER COLUMN `Inactive` DROP DEFAULT;

ALTER TABLE `ImageInstance` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `ImageInstance` ALTER COLUMN `DateModified` DROP DEFAULT;

ALTER TABLE `ImageInstanceTag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Model` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `ModelSegmentation` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Patient` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Project` ALTER COLUMN `External` DROP DEFAULT;

ALTER TABLE `Project` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Segmentation` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `SegmentationTag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Study` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `StudyTag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Tag` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `Task` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

ALTER TABLE `TaskDefinition` CHANGE `DateInserted` `DateInserted` DATETIME NOT NULL DEFAULT now();

UPDATE alembic_version SET version_num='ccb5ba8245c7' WHERE alembic_version.version_num = '048a18ac8486';

-- Running upgrade ccb5ba8245c7 -> eac6e6f7dcea

ALTER TABLE `ImageInstance` ADD COLUMN `AltDatasetIdentifier` VARCHAR(256);

ALTER TABLE `ImageInstance` MODIFY `Laterality` ENUM('L','R') NOT NULL;

ALTER TABLE `Series` ADD COLUMN `StudyInstanceUid` VARCHAR(64);

UPDATE `Series` AS s
        JOIN `Study` AS st ON s.StudyID = st.StudyID
        SET s.StudyInstanceUid = st.StudyInstanceUid
        WHERE st.StudyInstanceUid IS NOT NULL;

CREATE UNIQUE INDEX `StudyInstanceUidSeriesInstanceUid_UNIQUE` ON `Series` (`StudyInstanceUid`, `SeriesInstanceUid`);

DROP INDEX `StudyInstanceUid_UNIQUE` ON `Study`;

ALTER TABLE `Study` DROP COLUMN `StudyInstanceUid`;

UPDATE alembic_version SET version_num='eac6e6f7dcea' WHERE alembic_version.version_num = 'ccb5ba8245c7';

-- Running upgrade eac6e6f7dcea -> c5744885fe94

ALTER TABLE `FormAnnotation` ADD COLUMN `Laterality` ENUM('L','R');

ALTER TABLE `FormSchema` ADD COLUMN `EntityType` ENUM('Patient','Study','Eye','StudyEye','ImageInstance');

UPDATE FormAnnotation AS fa
        JOIN ImageInstance AS ii ON fa.ImageInstanceID = ii.ImageInstanceID
        SET fa.Laterality = ii.Laterality
        WHERE fa.ImageInstanceID IS NOT NULL;

UPDATE alembic_version SET version_num='c5744885fe94' WHERE alembic_version.version_num = 'eac6e6f7dcea';

-- Running upgrade c5744885fe94 -> 65eaddf0f0f8

CREATE INDEX `ix_FormAnnotation_FormAnnotationReferenceID` ON `FormAnnotation` (`FormAnnotationReferenceID`);

ALTER TABLE `FormAnnotationTag` ADD COLUMN `Comment` VARCHAR(256);

ALTER TABLE `ImageInstance` MODIFY `Inactive` TINYINT(1) NOT NULL DEFAULT '0';

ALTER TABLE `ImageInstanceTag` ADD COLUMN `Comment` VARCHAR(256);

ALTER TABLE `SegmentationTag` ADD COLUMN `Comment` VARCHAR(256);

ALTER TABLE `StudyTag` ADD COLUMN `Comment` VARCHAR(256);

UPDATE alembic_version SET version_num='65eaddf0f0f8' WHERE alembic_version.version_num = 'c5744885fe94';

-- Running upgrade 65eaddf0f0f8 -> 10d5ab598dc7

ALTER TABLE `AttributeValue` ADD COLUMN `PatientID` INTEGER;

ALTER TABLE `AttributeValue` ADD COLUMN `StudyID` INTEGER;

ALTER TABLE `AttributeValue` ADD COLUMN `Laterality` ENUM('L','R');

CREATE INDEX `fk_AttributeValue_Patient1_idx` ON `AttributeValue` (`PatientID`);

CREATE INDEX `fk_AttributeValue_Study1_idx` ON `AttributeValue` (`StudyID`);

ALTER TABLE `AttributeValue` ADD CONSTRAINT `uq_AttributeValue_patient_attribute_model` UNIQUE (`PatientID`, `AttributeID`, `ModelID`);

ALTER TABLE `AttributeValue` ADD CONSTRAINT `uq_AttributeValue_study_attribute_model` UNIQUE (`StudyID`, `AttributeID`, `ModelID`);

ALTER TABLE `AttributeValue` ADD FOREIGN KEY(`StudyID`) REFERENCES `Study` (`StudyID`);

ALTER TABLE `AttributeValue` ADD FOREIGN KEY(`PatientID`) REFERENCES `Patient` (`PatientID`);

UPDATE alembic_version SET version_num='10d5ab598dc7' WHERE alembic_version.version_num = '65eaddf0f0f8';

-- Running upgrade 10d5ab598dc7 -> 617b4b980d71

ALTER TABLE `AttributeValue` MODIFY `ModelID` INTEGER NULL;

ALTER TABLE `ImageInstance` MODIFY `ModalityID` INTEGER NULL;

UPDATE alembic_version SET version_num='617b4b980d71' WHERE alembic_version.version_num = '10d5ab598dc7';

-- Running upgrade 617b4b980d71 -> 13a6246c9119

ALTER TABLE `ImageInstance` MODIFY `Laterality` ENUM('L','R') NULL;

UPDATE alembic_version SET version_num='13a6246c9119' WHERE alembic_version.version_num = '617b4b980d71';

-- Running upgrade 13a6246c9119 -> 335c6bcc1fd8

CREATE INDEX `ix_AnnotationTag_Annotation_Tag` ON `AnnotationTag` (`AnnotationID`, `TagID`);

CREATE INDEX `ix_AttributeValue_ImageInstance_Attribute` ON `AttributeValue` (`ImageInstanceID`, `AttributeID`);

CREATE INDEX `ix_AttributeValue_ModelSegmentation_Attribute` ON `AttributeValue` (`ModelSegmentationID`, `AttributeID`);

CREATE INDEX `ix_AttributeValue_Patient_Attribute` ON `AttributeValue` (`PatientID`, `AttributeID`);

CREATE INDEX `ix_AttributeValue_Segmentation_Attribute` ON `AttributeValue` (`SegmentationID`, `AttributeID`);

CREATE INDEX `ix_AttributeValue_Study_Attribute` ON `AttributeValue` (`StudyID`, `AttributeID`);

CREATE INDEX `ix_FormAnnotation_FormSchema_Inactive_Creator` ON `FormAnnotation` (`FormSchemaID`, `Inactive`, `CreatorID`);

CREATE INDEX `ix_FormAnnotation_Image_Laterality_Inactive` ON `FormAnnotation` (`ImageInstanceID`, `Laterality`, `Inactive`);

CREATE INDEX `ix_FormAnnotation_Patient_Study_Inactive` ON `FormAnnotation` (`PatientID`, `StudyID`, `Inactive`);

CREATE INDEX `ix_FormAnnotation_SubTask_Inactive` ON `FormAnnotation` (`SubTaskID`, `Inactive`);

CREATE INDEX `ix_FormAnnotationTag_Form_Tag` ON `FormAnnotationTag` (`FormAnnotationID`, `TagID`);

CREATE INDEX `fk_ImageInstance_Series_Inactive1_idx` ON `ImageInstance` (`SeriesID`, `Inactive`);

CREATE INDEX `ix_ImageInstance_Modality_Inactive_ETDRSField` ON `ImageInstance` (`Modality`, `Inactive`, `ETDRSField`);

CREATE INDEX `ix_ImageInstance_Modality_Inactive_Laterality` ON `ImageInstance` (`Modality`, `Inactive`, `Laterality`);

CREATE INDEX `ix_ImageInstanceTag_Image_Tag` ON `ImageInstanceTag` (`ImageInstanceID`, `TagID`);

CREATE INDEX `ix_ModelSegmentation_Image_Model` ON `ModelSegmentation` (`ImageInstanceID`, `ModelID`);

CREATE INDEX `ix_ModelSegmentation_Model_Image` ON `ModelSegmentation` (`ModelID`, `ImageInstanceID`);

DROP INDEX `ProjectIDPatientIdentifier_UNIQUE` ON `Patient`;

CREATE UNIQUE INDEX `ProjectIDPatientIdentifier_UNIQUE` ON `Patient` (`ProjectID`, `PatientIdentifier`);

CREATE INDEX `ix_Patient_Project_Sex_BirthDate` ON `Patient` (`ProjectID`, `Sex`, `BirthDate`);

CREATE INDEX `ix_Segmentation_Feature_Inactive` ON `Segmentation` (`FeatureID`, `Inactive`);

CREATE INDEX `ix_Segmentation_Image_Feature_Inactive` ON `Segmentation` (`ImageInstanceID`, `FeatureID`, `Inactive`);

CREATE INDEX `ix_Segmentation_SubTask_Feature` ON `Segmentation` (`SubTaskID`, `FeatureID`);

CREATE INDEX `ix_SegmentationTag_Segmentation_Tag` ON `SegmentationTag` (`SegmentationID`, `TagID`);

CREATE INDEX `ix_Series_StudyID_SeriesNumber` ON `Series` (`StudyID`, `SeriesNumber`);

CREATE INDEX `ix_Series_StudyID_StudyInstanceUid` ON `Series` (`StudyID`, `StudyInstanceUid`);

DROP INDEX `PatientIDStudyDate_UNIQUE` ON `Study`;

CREATE UNIQUE INDEX `PatientIDStudyDate_UNIQUE` ON `Study` (`PatientID`, `StudyDate`);

CREATE INDEX `ix_Study_PatientID_StudyRound` ON `Study` (`PatientID`, `StudyRound`);

CREATE INDEX `ix_Study_StudyRound_StudyDate` ON `Study` (`StudyRound`, `StudyDate`);

CREATE INDEX `ix_StudyTag_Study_Tag` ON `StudyTag` (`StudyID`, `TagID`);

CREATE INDEX `ix_SubTask_TaskState_Creator` ON `SubTask` (`TaskState`, `CreatorID`);

CREATE INDEX `ix_SubTaskImageLink_Image_SubTask` ON `SubTaskImageLink` (`ImageInstanceID`, `SubTaskID`);

CREATE INDEX `ix_Task_Creator_TaskDefinition` ON `Task` (`CreatorID`, `TaskDefinitionID`);

UPDATE alembic_version SET version_num='335c6bcc1fd8' WHERE alembic_version.version_num = '13a6246c9119';

-- Running upgrade 335c6bcc1fd8 -> e4247389063f

CREATE INDEX `ix_Patient_PatientIdentifier` ON `Patient` (`PatientIdentifier`);

ALTER TABLE `SubTaskImageLink` ADD COLUMN `ImageIndex` INTEGER NOT NULL;

SET @idx := -1;

SET @prev_subtask := NULL;

UPDATE SubTaskImageLink
        SET ImageIndex = IF(
            @prev_subtask = SubTaskID,
            @idx := @idx + 1,
            @idx := IF(@prev_subtask := SubTaskID, 0, 0)
        )
        ORDER BY SubTaskID;

ALTER TABLE `SubTaskImageLink` MODIFY `ImageIndex` INTEGER NOT NULL;

ALTER TABLE `SubTaskImageLink` ADD CONSTRAINT `uq_SubTaskImageLink_SubTask_ImageIndex` UNIQUE (`SubTaskID`, `ImageIndex`);

UPDATE alembic_version SET version_num='e4247389063f' WHERE alembic_version.version_num = '335c6bcc1fd8';

-- Running upgrade e4247389063f -> 533b4abe81b9

CREATE TABLE `StorageBackend` (
    `StorageBackendID` INTEGER NOT NULL AUTO_INCREMENT, 
    `Key` VARCHAR(256) NOT NULL, 
    `Kind` VARCHAR(256) NOT NULL, 
    `Config` JSON NOT NULL, 
    PRIMARY KEY (`StorageBackendID`)
);

ALTER TABLE `ImageInstance` ADD COLUMN `PublicID` VARCHAR(12);

ALTER TABLE `ImageInstance` ADD COLUMN `StorageBackendID` INTEGER;

ALTER TABLE `ImageInstance` ADD COLUMN `ObjectPrefix` VARCHAR(256);

ALTER TABLE `ImageInstance` ADD COLUMN `ObjectKey` VARCHAR(256) NOT NULL;

-- NOTE: Data migration for storage backends and public IDs must be run manually or in online mode.;

ALTER TABLE `ImageInstance` MODIFY `PublicID` VARCHAR(12) NOT NULL;

ALTER TABLE `ImageInstance` MODIFY `StorageBackendID` INTEGER NOT NULL;

ALTER TABLE `ImageInstance` ADD CONSTRAINT `uq_ImageInstance_PublicID` UNIQUE (`PublicID`);

CREATE UNIQUE INDEX `ix_ImageInstance_PublicID` ON `ImageInstance` (`PublicID`);

ALTER TABLE `ImageInstance` ADD CONSTRAINT `fk_ImageInstance_StorageBackend` FOREIGN KEY(`StorageBackendID`) REFERENCES `StorageBackend` (`StorageBackendID`);

UPDATE alembic_version SET version_num='533b4abe81b9' WHERE alembic_version.version_num = 'e4247389063f';

-- Running upgrade 533b4abe81b9 -> 590cff943534

ALTER TABLE `ModelSegmentation` DROP FOREIGN KEY `ModelSegmentation_ibfk_3`;

ALTER TABLE `ModelSegmentation` DROP COLUMN `ReferenceSegmentationID`;

UPDATE alembic_version SET version_num='590cff943534' WHERE alembic_version.version_num = '533b4abe81b9';

