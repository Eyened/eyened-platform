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

-- Running upgrade 62b55e9c9e70 -> 5ffd55a02beb

ALTER TABLE `ImageInstance` ADD COLUMN `AltDatasetIdentifier` VARCHAR(256);

ALTER TABLE `ImageInstance` MODIFY `Laterality` ENUM('L','R') NOT NULL;

ALTER TABLE `Series` ADD COLUMN `StudyInstanceUid` VARCHAR(64);

UPDATE `Series` AS s
JOIN `Study` AS st ON s.StudyID = st.StudyID
SET s.StudyInstanceUid = st.StudyInstanceUid
WHERE st.StudyInstanceUid IS NOT NULL

CREATE UNIQUE INDEX `StudyInstanceUidSeriesInstanceUid_UNIQUE` ON `Series` (`StudyInstanceUid`, `SeriesInstanceUid`);

DROP INDEX `StudyInstanceUid_UNIQUE` ON `Study`;

ALTER TABLE `Study` DROP COLUMN `StudyInstanceUid`;

UPDATE alembic_version SET version_num='5ffd55a02beb' WHERE alembic_version.version_num = '62b55e9c9e70';

