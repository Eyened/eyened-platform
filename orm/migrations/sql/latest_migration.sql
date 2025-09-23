-- Running upgrade 832ed384515f -> e69c5e4002ed

CREATE TABLE `CompositeFeature` (
    `ParentFeatureID` INTEGER NOT NULL, 
    `ChildFeatureID` INTEGER NOT NULL, 
    `FeatureIndex` INTEGER NOT NULL, 
    PRIMARY KEY (`ParentFeatureID`, `ChildFeatureID`, `FeatureIndex`), 
    FOREIGN KEY(`ChildFeatureID`) REFERENCES `Feature` (`FeatureID`), 
    FOREIGN KEY(`ParentFeatureID`) REFERENCES `Feature` (`FeatureID`)
);

CREATE INDEX `fk_CompositeFeature_ChildFeature1_idx` ON `CompositeFeature` (`ChildFeatureID`);

CREATE INDEX `fk_CompositeFeature_ParentFeature1_idx` ON `CompositeFeature` (`ParentFeatureID`);

CREATE TABLE `Model` (
    `ModelName` VARCHAR(255) NOT NULL, 
    `Version` VARCHAR(255) NOT NULL, 
    `ModelType` VARCHAR(255) NOT NULL, 
    `Description` VARCHAR(255), 
    `FeatureID` INTEGER NOT NULL, 
    `ModelID` INTEGER NOT NULL AUTO_INCREMENT, 
    `DateInserted` DATETIME NOT NULL, 
    PRIMARY KEY (`ModelID`), 
    FOREIGN KEY(`FeatureID`) REFERENCES `Feature` (`FeatureID`), 
    UNIQUE (`ModelName`), 
    UNIQUE (`ModelName`, `Version`), 
    UNIQUE (`Version`)
);

CREATE TABLE `Segmentation` (
    `ZarrArrayIndex` INTEGER, 
    `ImageInstanceID` INTEGER, 
    `Depth` INTEGER NOT NULL, 
    `Height` INTEGER NOT NULL, 
    `Width` INTEGER NOT NULL, 
    `SparseAxis` INTEGER, 
    `ImageProjectionMatrix` JSON, 
    `ScanIndices` JSON, 
    `DataRepresentation` ENUM('Binary','DualBitMask','Probability','MultiLabel','MultiClass') NOT NULL, 
    `DataType` ENUM('R8','R8UI','R16UI','R32UI','R32F') NOT NULL, 
    `Threshold` FLOAT, 
    `ReferenceSegmentationID` INTEGER, 
    `SegmentationID` INTEGER NOT NULL AUTO_INCREMENT, 
    `CreatorID` INTEGER NOT NULL, 
    `FeatureID` INTEGER NOT NULL, 
    `SubTaskID` INTEGER, 
    `DateInserted` DATETIME NOT NULL, 
    `DateModified` DATETIME, 
    `Inactive` BOOL NOT NULL, 
    PRIMARY KEY (`SegmentationID`), 
    FOREIGN KEY(`CreatorID`) REFERENCES `Creator` (`CreatorID`), 
    FOREIGN KEY(`FeatureID`) REFERENCES `Feature` (`FeatureID`), 
    FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ReferenceSegmentationID`) REFERENCES `Segmentation` (`SegmentationID`), 
    FOREIGN KEY(`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`)
);

CREATE TABLE `ModelSegmentation` (
    `ZarrArrayIndex` INTEGER, 
    `ImageInstanceID` INTEGER, 
    `Depth` INTEGER NOT NULL, 
    `Height` INTEGER NOT NULL, 
    `Width` INTEGER NOT NULL, 
    `SparseAxis` INTEGER, 
    `ImageProjectionMatrix` JSON, 
    `ScanIndices` JSON, 
    `DataRepresentation` ENUM('Binary','DualBitMask','Probability','MultiLabel','MultiClass') NOT NULL, 
    `DataType` ENUM('R8','R8UI','R16UI','R32UI','R32F') NOT NULL, 
    `Threshold` FLOAT, 
    `ReferenceSegmentationID` INTEGER, 
    `SegmentationID` INTEGER NOT NULL AUTO_INCREMENT, 
    `ModelID` INTEGER NOT NULL, 
    `DateInserted` DATETIME NOT NULL, 
    PRIMARY KEY (`SegmentationID`), 
    FOREIGN KEY(`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE, 
    FOREIGN KEY(`ModelID`) REFERENCES `Model` (`ModelID`), 
    FOREIGN KEY(`ReferenceSegmentationID`) REFERENCES `Segmentation` (`SegmentationID`)
);

CREATE TABLE `SegmentationTag` (
    `TagID` INTEGER NOT NULL, 
    `SegmentationID` INTEGER NOT NULL, 
    PRIMARY KEY (`TagID`, `SegmentationID`), 
    FOREIGN KEY(`SegmentationID`) REFERENCES `Segmentation` (`SegmentationID`), 
    FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`)
);

CREATE INDEX `fk_SegmentationTag_Segmentation1_idx` ON `SegmentationTag` (`SegmentationID`);

CREATE INDEX `fk_SegmentationTag_Tag1_idx` ON `SegmentationTag` (`TagID`);

CREATE TABLE `FormAnnotationTag` (
    `TagID` INTEGER NOT NULL, 
    `FormAnnotationID` INTEGER NOT NULL, 
    PRIMARY KEY (`TagID`, `FormAnnotationID`), 
    FOREIGN KEY(`FormAnnotationID`) REFERENCES `FormAnnotation` (`FormAnnotationID`), 
    FOREIGN KEY(`TagID`) REFERENCES `Tag` (`TagID`)
);

CREATE INDEX `fk_FormAnnotationTag_FormAnnotation1_idx` ON `FormAnnotationTag` (`FormAnnotationID`);

CREATE INDEX `fk_FormAnnotationTag_Tag1_idx` ON `FormAnnotationTag` (`TagID`);

DROP TABLE `AnnotationTag`;

ALTER TABLE `Annotation` ADD FOREIGN KEY(`AnnotationReferenceID`) REFERENCES `Annotation` (`AnnotationID`);

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

ALTER TABLE `ImageInstance` MODIFY `DeviceInstanceID` INTEGER NOT NULL;

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

