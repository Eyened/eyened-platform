-- eyened-platform schema-sync CI baseline.
--
-- DO NOT LOAD THIS INTO A LIVE DATABASE. It is CI input only: the schema-sync
-- job loads it into a throwaway MySQL container, replays `alembic upgrade head`,
-- and asserts that `alembic check` reports no operations.
--
-- Contents: table definitions only (no row data) plus the single `alembic_version`
-- row, so loading it establishes schema and revision in one operation. There is no
-- `alembic stamp` step anywhere in the workflow.
--
-- Excluded on purpose: stored routines, triggers, and the six views that exist at
-- Erasmus production (ProjectToFeature, ProjectToImageInstance, ProjectToImageStorage,
-- ProjectToSubtask, ProjectToTag, Statistics). Alembic reflects base tables only, so
-- none of them can affect what this gate asserts, and each would arrive carrying a
-- production DEFINER clause.
--
-- Provenance: XtraBackup of Erasmus production taken 2026-07-28
-- (backup_type=full-prepared, server_version=8.0.27, partial=N, encrypted=N),
-- restored into a throwaway MySQL 8.0.27 container on 2026-08-17.
-- Restored database: eyened_database.  Revision, read by SELECT from alembic_version: a1d1700000a1.
--
-- Frozen artifact: new revisions replay on top of it, so it is not refreshed under
-- normal operation. Regeneration is manual — see README.md in this directory.

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Annotation` (
  `AnnotationID` int NOT NULL AUTO_INCREMENT,
  `PatientID` int NOT NULL,
  `StudyID` int DEFAULT NULL,
  `SeriesID` int DEFAULT NULL,
  `ImageInstanceID` int DEFAULT NULL,
  `AnnotationReferenceID` int DEFAULT NULL,
  `CreatorID` int NOT NULL,
  `FeatureID` int NOT NULL,
  `AnnotationTypeID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Inactive` tinyint(1) NOT NULL,
  PRIMARY KEY (`AnnotationID`),
  KEY `fk_Annotation_AnnotationType1_idx` (`AnnotationTypeID`),
  KEY `fk_Annotation_Creator1_idx` (`CreatorID`),
  KEY `fk_Annotation_Feature1_idx` (`FeatureID`),
  KEY `fk_Annotation_ImageInstance1_idx` (`ImageInstanceID`),
  KEY `fk_Annotation_Study1_idx` (`StudyID`),
  KEY `fk_Annotation_Patient1_idx` (`PatientID`),
  KEY `fk_Annotation_Series1_idx` (`SeriesID`),
  KEY `AnnotationReferenceID` (`AnnotationReferenceID`),
  CONSTRAINT `Annotation_ibfk_1` FOREIGN KEY (`AnnotationReferenceID`) REFERENCES `Annotation` (`AnnotationID`) ON DELETE CASCADE,
  CONSTRAINT `fk_Annotation_AnnotationType1` FOREIGN KEY (`AnnotationTypeID`) REFERENCES `AnnotationType` (`AnnotationTypeID`),
  CONSTRAINT `fk_Annotation_Features1` FOREIGN KEY (`FeatureID`) REFERENCES `Feature` (`FeatureID`),
  CONSTRAINT `fk_Annotation_Grader1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `fk_Annotation_ImageInstance1` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `fk_Annotation_Patient1` FOREIGN KEY (`PatientID`) REFERENCES `Patient` (`PatientID`),
  CONSTRAINT `fk_Annotation_Series1` FOREIGN KEY (`SeriesID`) REFERENCES `Series` (`SeriesID`),
  CONSTRAINT `fk_Annotation_Study1` FOREIGN KEY (`StudyID`) REFERENCES `Study` (`StudyID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AnnotationData` (
  `AnnotationID` int NOT NULL,
  `ScanNr` int NOT NULL,
  `DatasetIdentifier` varchar(45) NOT NULL,
  `MediaType` varchar(45) NOT NULL,
  `DateModified` datetime ON UPDATE CURRENT_TIMESTAMP,
  `ValueInt` int DEFAULT NULL,
  `ValueFloat` float DEFAULT NULL,
  `ValueBlob` longblob,
  PRIMARY KEY (`AnnotationID`,`ScanNr`),
  UNIQUE KEY `DatasetIdentifier_UNIQUE` (`DatasetIdentifier`),
  KEY `fk_AnnotationData_Annotation1_idx` (`AnnotationID`),
  CONSTRAINT `fk_AnnotationData_Annotation1` FOREIGN KEY (`AnnotationID`) REFERENCES `Annotation` (`AnnotationID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AnnotationTag` (
  `TagID` int NOT NULL,
  `AnnotationID` int NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`TagID`,`AnnotationID`),
  KEY `fk_AnnotationTag_Annotation1_idx` (`AnnotationID`),
  KEY `fk_AnnotationTag_Creator1_idx` (`CreatorID`),
  KEY `fk_AnnotationTag_Tag1_idx` (`TagID`),
  KEY `ix_AnnotationTag_Annotation_Tag` (`AnnotationID`,`TagID`),
  CONSTRAINT `AnnotationTag_ibfk_2` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `AnnotationTag_ibfk_3` FOREIGN KEY (`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE,
  CONSTRAINT `AnnotationTag_ibfk_4` FOREIGN KEY (`AnnotationID`) REFERENCES `Annotation` (`AnnotationID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AnnotationType` (
  `AnnotationTypeID` int NOT NULL AUTO_INCREMENT,
  `AnnotationTypeName` varchar(45) NOT NULL,
  `Interpretation` varchar(45) CHARACTER SET utf8 COLLATE utf8_general_ci NOT NULL,
  PRIMARY KEY (`AnnotationTypeID`),
  UNIQUE KEY `AnnotationTypeNameInterpretation_UNIQUE` (`AnnotationTypeName`,`Interpretation`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AttributeDefinition` (
  `AttributeID` int NOT NULL AUTO_INCREMENT,
  `AttributeName` varchar(255) NOT NULL,
  `AttributeDataType` enum('String','Float','Int','JSON') NOT NULL,
  PRIMARY KEY (`AttributeID`),
  UNIQUE KEY `uq_AttributeDefinition_AttributeName` (`AttributeName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AttributeValue` (
  `AttributeValueID` int NOT NULL AUTO_INCREMENT,
  `AttributeID` int NOT NULL,
  `ModelID` int DEFAULT NULL,
  `ImageInstanceID` int DEFAULT NULL,
  `SegmentationID` int DEFAULT NULL,
  `ModelSegmentationID` int DEFAULT NULL,
  `ValueFloat` float DEFAULT NULL,
  `ValueInt` int DEFAULT NULL,
  `ValueText` varchar(255) DEFAULT NULL,
  `ValueJSON` json DEFAULT NULL,
  `PatientID` int DEFAULT NULL,
  `StudyID` int DEFAULT NULL,
  `Laterality` enum('L','R') DEFAULT NULL,
  PRIMARY KEY (`AttributeValueID`),
  UNIQUE KEY `uq_AttributeValue_image_attribute_model` (`ImageInstanceID`,`AttributeID`,`ModelID`),
  UNIQUE KEY `uq_AttributeValue_modelseg_attribute_model` (`ModelSegmentationID`,`AttributeID`,`ModelID`),
  UNIQUE KEY `uq_AttributeValue_segmentation_attribute_model` (`SegmentationID`,`AttributeID`,`ModelID`),
  UNIQUE KEY `uq_AttributeValue_patient_attribute_model` (`PatientID`,`AttributeID`,`ModelID`),
  UNIQUE KEY `uq_AttributeValue_study_attribute_model` (`StudyID`,`AttributeID`,`ModelID`),
  KEY `fk_AttributeValue_Attribute1_idx` (`AttributeID`),
  KEY `fk_AttributeValue_ImageInstance1_idx` (`ImageInstanceID`),
  KEY `fk_AttributeValue_Model1_idx` (`ModelID`),
  KEY `fk_AttributeValue_ModelSegmentation1_idx` (`ModelSegmentationID`),
  KEY `fk_AttributeValue_Segmentation1_idx` (`SegmentationID`),
  KEY `fk_AttributeValue_Patient1_idx` (`PatientID`),
  KEY `fk_AttributeValue_Study1_idx` (`StudyID`),
  KEY `ix_AttributeValue_ImageInstance_Attribute` (`ImageInstanceID`,`AttributeID`),
  KEY `ix_AttributeValue_ModelSegmentation_Attribute` (`ModelSegmentationID`,`AttributeID`),
  KEY `ix_AttributeValue_Patient_Attribute` (`PatientID`,`AttributeID`),
  KEY `ix_AttributeValue_Segmentation_Attribute` (`SegmentationID`,`AttributeID`),
  KEY `ix_AttributeValue_Study_Attribute` (`StudyID`,`AttributeID`),
  CONSTRAINT `AttributeValue_ibfk_1` FOREIGN KEY (`AttributeID`) REFERENCES `AttributeDefinition` (`AttributeID`) ON DELETE CASCADE,
  CONSTRAINT `AttributeValue_ibfk_2` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `AttributeValue_ibfk_3` FOREIGN KEY (`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE,
  CONSTRAINT `AttributeValue_ibfk_4` FOREIGN KEY (`ModelSegmentationID`) REFERENCES `ModelSegmentation` (`ModelSegmentationID`) ON DELETE CASCADE,
  CONSTRAINT `AttributeValue_ibfk_5` FOREIGN KEY (`SegmentationID`) REFERENCES `Segmentation` (`SegmentationID`) ON DELETE CASCADE,
  CONSTRAINT `AttributeValue_ibfk_6` FOREIGN KEY (`StudyID`) REFERENCES `Study` (`StudyID`),
  CONSTRAINT `AttributeValue_ibfk_7` FOREIGN KEY (`PatientID`) REFERENCES `Patient` (`PatientID`),
  CONSTRAINT `ck_AttributeValue_exactly_one_entity` CHECK ((((`ImageInstanceID` is not null) and (`SegmentationID` is null) and (`ModelSegmentationID` is null) and (`PatientID` is null) and (`StudyID` is null)) or ((`ImageInstanceID` is null) and (`SegmentationID` is not null) and (`ModelSegmentationID` is null) and (`PatientID` is null) and (`StudyID` is null)) or ((`ImageInstanceID` is null) and (`SegmentationID` is null) and (`ModelSegmentationID` is not null) and (`PatientID` is null) and (`StudyID` is null)) or ((`ImageInstanceID` is null) and (`SegmentationID` is null) and (`ModelSegmentationID` is null) and (`PatientID` is not null) and (`StudyID` is null)) or ((`ImageInstanceID` is null) and (`SegmentationID` is null) and (`ModelSegmentationID` is null) and (`PatientID` is null) and (`StudyID` is not null))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AttributeValueInput` (
  `OutputAttributeValueID` int NOT NULL,
  `InputAttributeValueID` int NOT NULL,
  PRIMARY KEY (`OutputAttributeValueID`,`InputAttributeValueID`),
  KEY `InputAttributeValueID` (`InputAttributeValueID`),
  CONSTRAINT `AttributeValueInput_ibfk_1` FOREIGN KEY (`InputAttributeValueID`) REFERENCES `AttributeValue` (`AttributeValueID`) ON DELETE CASCADE,
  CONSTRAINT `AttributeValueInput_ibfk_2` FOREIGN KEY (`OutputAttributeValueID`) REFERENCES `AttributeValue` (`AttributeValueID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AttributesModel` (
  `ModelID` int NOT NULL,
  PRIMARY KEY (`ModelID`),
  CONSTRAINT `AttributesModel_ibfk_1` FOREIGN KEY (`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AttributesModelOutput` (
  `ModelID` int NOT NULL,
  `AttributeID` int NOT NULL,
  PRIMARY KEY (`ModelID`,`AttributeID`),
  KEY `AttributeID` (`AttributeID`),
  CONSTRAINT `AttributesModelOutput_ibfk_1` FOREIGN KEY (`AttributeID`) REFERENCES `AttributeDefinition` (`AttributeID`) ON DELETE CASCADE,
  CONSTRAINT `AttributesModelOutput_ibfk_2` FOREIGN KEY (`ModelID`) REFERENCES `AttributesModel` (`ModelID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `AuditLog` (
  `AuditLogID` int NOT NULL AUTO_INCREMENT,
  `Timestamp` datetime NOT NULL,
  `ActorID` int DEFAULT NULL,
  `TrustedPath` varchar(255) DEFAULT NULL,
  `Action` varchar(16) NOT NULL,
  `Entity` varchar(64) NOT NULL,
  `EntityID` varchar(255) DEFAULT NULL,
  `ProjectID` int DEFAULT NULL,
  `Changes` json DEFAULT NULL,
  PRIMARY KEY (`AuditLogID`),
  KEY `ix_AuditLog_ActorID` (`ActorID`),
  KEY `ix_AuditLog_Timestamp` (`Timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `CompositeFeature` (
  `ParentFeatureID` int NOT NULL,
  `ChildFeatureID` int NOT NULL,
  `FeatureIndex` int NOT NULL,
  PRIMARY KEY (`ParentFeatureID`,`ChildFeatureID`,`FeatureIndex`),
  KEY `fk_CompositeFeature_ChildFeature1_idx` (`ChildFeatureID`),
  KEY `fk_CompositeFeature_ParentFeature1_idx` (`ParentFeatureID`),
  CONSTRAINT `CompositeFeature_ibfk_1` FOREIGN KEY (`ChildFeatureID`) REFERENCES `Feature` (`FeatureID`),
  CONSTRAINT `CompositeFeature_ibfk_2` FOREIGN KEY (`ParentFeatureID`) REFERENCES `Feature` (`FeatureID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Contact` (
  `ContactID` int NOT NULL AUTO_INCREMENT,
  `Name` varchar(255) NOT NULL,
  `Email` varchar(255) NOT NULL,
  `Institute` varchar(255) DEFAULT NULL,
  `Orcid` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`ContactID`),
  UNIQUE KEY `NameEmailInstitute_UNIQUE` (`Name`,`Email`,`Institute`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Creator` (
  `CreatorID` int NOT NULL AUTO_INCREMENT,
  `CreatorName` varchar(45) NOT NULL,
  `EmployeeIdentifier` varchar(255) DEFAULT NULL,
  `IsHuman` tinyint NOT NULL,
  `Path` varchar(80) DEFAULT NULL,
  `Description` varchar(1000) DEFAULT NULL,
  `Version` int DEFAULT NULL,
  `Password` binary(32) DEFAULT NULL,
  `Role` int DEFAULT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `PasswordHash` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`CreatorID`),
  UNIQUE KEY `CreatorName_UNIQUE` (`CreatorName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `CreatorTag` (
  `TagID` int NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`TagID`,`CreatorID`),
  KEY `fk_CreatorTag_Creator1_idx` (`CreatorID`),
  KEY `fk_CreatorTag_Tag1_idx` (`TagID`),
  CONSTRAINT `CreatorTag_ibfk_1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`) ON DELETE CASCADE,
  CONSTRAINT `CreatorTag_ibfk_2` FOREIGN KEY (`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `DeviceInstance` (
  `DeviceInstanceID` int NOT NULL AUTO_INCREMENT,
  `DeviceModelID` int NOT NULL,
  `SerialNumber` text,
  `Description` varchar(256) NOT NULL,
  PRIMARY KEY (`DeviceInstanceID`),
  UNIQUE KEY `DeviceModelIDDescription_UNIQUE` (`DeviceModelID`,`Description`),
  CONSTRAINT `fk_DeviceInstance_DeviceModel1` FOREIGN KEY (`DeviceModelID`) REFERENCES `DeviceModel` (`DeviceModelID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `DeviceModel` (
  `DeviceModelID` int NOT NULL AUTO_INCREMENT,
  `Manufacturer` varchar(45) NOT NULL,
  `ManufacturerModelName` varchar(45) NOT NULL,
  PRIMARY KEY (`DeviceModelID`),
  UNIQUE KEY `ManufacturerManufacturerModelName_UNIQUE` (`Manufacturer`,`ManufacturerModelName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Feature` (
  `FeatureID` int NOT NULL AUTO_INCREMENT,
  `FeatureName` varchar(60) NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`FeatureID`),
  UNIQUE KEY `FeatureName_UNIQUE` (`FeatureName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `FormAnnotation` (
  `FormAnnotationID` int NOT NULL AUTO_INCREMENT,
  `FormSchemaID` int NOT NULL,
  `PatientID` int NOT NULL,
  `StudyID` int DEFAULT NULL,
  `ImageInstanceID` int DEFAULT NULL,
  `CreatorID` int NOT NULL,
  `SubTaskID` int DEFAULT NULL,
  `FormData` json DEFAULT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `DateModified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `Inactive` tinyint(1) NOT NULL,
  `FormAnnotationReferenceID` int DEFAULT NULL,
  `Laterality` enum('L','R') DEFAULT NULL,
  PRIMARY KEY (`FormAnnotationID`),
  KEY `CreatorID` (`CreatorID`),
  KEY `FormSchemaID` (`FormSchemaID`),
  KEY `ImageInstanceID` (`ImageInstanceID`),
  KEY `PatientID` (`PatientID`),
  KEY `StudyID` (`StudyID`),
  KEY `SubTaskID` (`SubTaskID`),
  KEY `ix_FormAnnotation_FormAnnotationReferenceID` (`FormAnnotationReferenceID`),
  KEY `ix_FormAnnotation_FormSchema_Inactive_Creator` (`FormSchemaID`,`Inactive`,`CreatorID`),
  KEY `ix_FormAnnotation_Image_Laterality_Inactive` (`ImageInstanceID`,`Laterality`,`Inactive`),
  KEY `ix_FormAnnotation_Patient_Study_Inactive` (`PatientID`,`StudyID`,`Inactive`),
  KEY `ix_FormAnnotation_SubTask_Inactive` (`SubTaskID`,`Inactive`),
  CONSTRAINT `fk_FormAnnotation_Creator1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `fk_FormAnnotation_FormAnnotationReferenceID` FOREIGN KEY (`FormAnnotationReferenceID`) REFERENCES `FormAnnotation` (`FormAnnotationID`) ON DELETE CASCADE,
  CONSTRAINT `fk_FormAnnotation_FormSchema1` FOREIGN KEY (`FormSchemaID`) REFERENCES `FormSchema` (`FormSchemaID`),
  CONSTRAINT `fk_FormAnnotation_Patient1` FOREIGN KEY (`PatientID`) REFERENCES `Patient` (`PatientID`),
  CONSTRAINT `fk_FormAnnotation_Study1` FOREIGN KEY (`StudyID`) REFERENCES `Study` (`StudyID`),
  CONSTRAINT `FormAnnotation_ibfk_1` FOREIGN KEY (`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE SET NULL,
  CONSTRAINT `FormAnnotation_ibfk_2` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `FormAnnotation_ibfk_3` FOREIGN KEY (`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `FormAnnotationTag` (
  `TagID` int NOT NULL,
  `FormAnnotationID` int NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Comment` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`TagID`,`FormAnnotationID`),
  KEY `fk_FormAnnotationTag_FormAnnotation1_idx` (`FormAnnotationID`),
  KEY `fk_FormAnnotationTag_Tag1_idx` (`TagID`),
  KEY `fk_FormAnnotationTag_Creator1_idx` (`CreatorID`),
  KEY `ix_FormAnnotationTag_Form_Tag` (`FormAnnotationID`,`TagID`),
  CONSTRAINT `FormAnnotationTag_ibfk_3` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `FormAnnotationTag_ibfk_4` FOREIGN KEY (`FormAnnotationID`) REFERENCES `FormAnnotation` (`FormAnnotationID`) ON DELETE CASCADE,
  CONSTRAINT `FormAnnotationTag_ibfk_5` FOREIGN KEY (`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `FormSchema` (
  `FormSchemaID` int NOT NULL AUTO_INCREMENT,
  `SchemaName` varchar(255) NOT NULL,
  `Schema` json DEFAULT NULL,
  `EntityType` enum('Patient','Study','Eye','StudyEye','ImageInstance') DEFAULT NULL,
  PRIMARY KEY (`FormSchemaID`),
  UNIQUE KEY `SchemaName_UNIQUE` (`SchemaName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ImageInstance` (
  `ImageInstanceID` int NOT NULL AUTO_INCREMENT,
  `SeriesID` int NOT NULL,
  `SourceInfoID` int DEFAULT NULL,
  `ScanID` int DEFAULT NULL,
  `DeviceInstanceID` int NOT NULL,
  `ModalityID` int DEFAULT NULL,
  `Modality` enum('AdaptiveOptics','ColorFundus','ColorFundusStereo','RedFreeFundus','ExternalEye','LensPhotograph','Ophthalmoscope','Autofluorescence','FluoresceinAngiography','ICGA','InfraredReflectance','BlueReflectance','GreenReflectance','OCT','OCTA') DEFAULT NULL,
  `DICOMModality` enum('OP','OPT','SC') DEFAULT NULL,
  `SOPInstanceUid` varchar(64) DEFAULT NULL,
  `SOPClassUid` varchar(64) DEFAULT NULL,
  `PhotometricInterpretation` varchar(64) DEFAULT NULL,
  `SamplesPerPixel` int DEFAULT NULL,
  `NrOfFrames` int DEFAULT NULL,
  `SliceThickness` float DEFAULT NULL,
  `Rows_y` int DEFAULT NULL,
  `Columns_x` int DEFAULT NULL,
  `Laterality` enum('L','R') DEFAULT NULL,
  `AnatomicRegion` int DEFAULT NULL,
  `Angiography` int DEFAULT NULL,
  `AcquisitionDateTime` datetime DEFAULT NULL,
  `PupilDilated` tinyint DEFAULT NULL,
  `HorizontalFieldOfView` float DEFAULT NULL,
  `ResolutionAxial` float DEFAULT NULL,
  `ResolutionHorizontal` float DEFAULT NULL,
  `ResolutionVertical` float DEFAULT NULL,
  `DatasetIdentifier` varchar(256) NOT NULL,
  `FDAIdentifier` int DEFAULT NULL,
  `OldPath` varchar(256) DEFAULT NULL,
  `ETDRSField` enum('F1','F2','F3','F4','F5','F6','F7') DEFAULT NULL,
  `CFROI` json DEFAULT NULL,
  `CFKeypoints` json DEFAULT NULL,
  `CFQuality` float DEFAULT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `DateModified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `DatePreprocessed` datetime DEFAULT NULL,
  `ThumbnailPath` varchar(256) DEFAULT NULL,
  `Inactive` tinyint(1) NOT NULL DEFAULT '0',
  `AltDatasetIdentifier` varchar(256) DEFAULT NULL,
  `PublicID` char(12) NOT NULL,
  PRIMARY KEY (`ImageInstanceID`),
  UNIQUE KEY `PublicID` (`PublicID`),
  UNIQUE KEY `SOPInstanceUid_UNIQUE` (`SOPInstanceUid`),
  KEY `fk_ImageInstance_Modality1_idx` (`ModalityID`),
  KEY `fk_ImageInstance_Scan1_idx` (`ScanID`),
  KEY `fk_ImageInstance_Series1_idx` (`SeriesID`),
  KEY `fk_ImageInstance_SourceInfo1_idx` (`SourceInfoID`),
  KEY `fk_ImageInstance_DeviceInstance1_idx` (`DeviceInstanceID`),
  KEY `DatasetIdentifier` (`DatasetIdentifier`),
  KEY `fk_ImageInstance_Series_Inactive1_idx` (`SeriesID`,`Inactive`),
  KEY `ix_ImageInstance_Modality_Inactive_ETDRSField` (`Modality`,`Inactive`,`ETDRSField`),
  KEY `ix_ImageInstance_Modality_Inactive_Laterality` (`Modality`,`Inactive`,`Laterality`),
  CONSTRAINT `fk_ImageInstance_DeviceInstance1` FOREIGN KEY (`DeviceInstanceID`) REFERENCES `DeviceInstance` (`DeviceInstanceID`),
  CONSTRAINT `fk_ImageInstance_Modality1` FOREIGN KEY (`ModalityID`) REFERENCES `Modality` (`ModalityID`),
  CONSTRAINT `fk_ImageInstance_Scan1` FOREIGN KEY (`ScanID`) REFERENCES `Scan` (`ScanID`),
  CONSTRAINT `fk_ImageInstance_Series1` FOREIGN KEY (`SeriesID`) REFERENCES `Series` (`SeriesID`) ON DELETE CASCADE,
  CONSTRAINT `fk_ImageInstance_Sources1` FOREIGN KEY (`SourceInfoID`) REFERENCES `SourceInfo` (`SourceInfoID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ImageInstanceTag` (
  `ImageInstanceID` int NOT NULL,
  `TagID` int NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Comment` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`ImageInstanceID`,`TagID`),
  KEY `fk_ImageInstanceTag_ImageInstance1_idx` (`ImageInstanceID`),
  KEY `fk_ImageInstanceTag_Tag1_idx` (`TagID`),
  KEY `fk_ImageInstanceTag_Creator1_idx` (`CreatorID`),
  KEY `ix_ImageInstanceTag_Image_Tag` (`ImageInstanceID`,`TagID`),
  CONSTRAINT `ImageInstanceTag_ibfk_1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `ImageInstanceTag_ibfk_2` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `ImageInstanceTag_ibfk_3` FOREIGN KEY (`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ImageStorage` (
  `ImageStorageID` int NOT NULL AUTO_INCREMENT,
  `ImageInstanceID` int NOT NULL,
  `StorageBackendID` int NOT NULL,
  `ObjectKey` varchar(256) NOT NULL,
  `Hash` binary(32) DEFAULT NULL,
  `Checksum` varchar(128) DEFAULT NULL,
  `Format` varchar(256) NOT NULL,
  `IsPrimary` tinyint(1) NOT NULL DEFAULT '1',
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `DateModified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ImageStorageID`),
  UNIQUE KEY `ObjectKey_StorageBackendID_UNIQUE` (`ObjectKey`,`StorageBackendID`),
  KEY `StorageBackendID` (`StorageBackendID`),
  KEY `ix_ImageStorage_ImageInstanceID_IsPrimary` (`ImageInstanceID`,`IsPrimary`),
  CONSTRAINT `ImageStorage_ibfk_1` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`),
  CONSTRAINT `ImageStorage_ibfk_2` FOREIGN KEY (`StorageBackendID`) REFERENCES `StorageBackend` (`StorageBackendID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Modality` (
  `ModalityID` int NOT NULL AUTO_INCREMENT,
  `ModalityTag` varchar(40) NOT NULL,
  PRIMARY KEY (`ModalityID`),
  UNIQUE KEY `ModalityTag_UNIQUE` (`ModalityTag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Model` (
  `ModelID` int NOT NULL AUTO_INCREMENT,
  `ModelName` varchar(255) NOT NULL,
  `Version` varchar(255) NOT NULL,
  `Description` varchar(255) DEFAULT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ModelType` enum('segmentation','attributes') NOT NULL,
  PRIMARY KEY (`ModelID`),
  UNIQUE KEY `ModelName_2` (`ModelName`,`Version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ModelInput` (
  `ModelInputID` int NOT NULL AUTO_INCREMENT,
  `ModelID` int NOT NULL,
  `InputAttributeID` int NOT NULL,
  `InputName` varchar(255) NOT NULL,
  PRIMARY KEY (`ModelInputID`),
  UNIQUE KEY `uq_ModelInput_ModelID_InputAttributeID` (`ModelID`,`InputAttributeID`),
  KEY `fk_ModelInput_Attribute1_idx` (`InputAttributeID`),
  KEY `fk_ModelInput_Model1_idx` (`ModelID`),
  CONSTRAINT `ModelInput_ibfk_1` FOREIGN KEY (`InputAttributeID`) REFERENCES `AttributeDefinition` (`AttributeID`) ON DELETE CASCADE,
  CONSTRAINT `ModelInput_ibfk_2` FOREIGN KEY (`ModelID`) REFERENCES `AttributesModel` (`ModelID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ModelSegmentation` (
  `ModelSegmentationID` int NOT NULL AUTO_INCREMENT,
  `ImageInstanceID` int NOT NULL,
  `ZarrArrayIndex` int DEFAULT NULL,
  `ModelID` int NOT NULL,
  `DataRepresentation` enum('Binary','DualBitMask','Probability','MultiLabel','MultiClass') NOT NULL,
  `DataType` enum('R8','R8UI','R16UI','R32UI','R32F') NOT NULL,
  `ScanIndices` json DEFAULT NULL,
  `SparseAxis` int DEFAULT NULL,
  `Depth` int NOT NULL,
  `Height` int NOT NULL,
  `Width` int NOT NULL,
  `ImageProjectionMatrix` json DEFAULT NULL,
  `Threshold` float DEFAULT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ModelSegmentationID`),
  KEY `ix_ModelSegmentation_Image_Model` (`ImageInstanceID`,`ModelID`),
  KEY `ix_ModelSegmentation_Model_Image` (`ModelID`,`ImageInstanceID`),
  CONSTRAINT `ModelSegmentation_ibfk_1` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `ModelSegmentation_ibfk_2` FOREIGN KEY (`ModelID`) REFERENCES `Model` (`ModelID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Patient` (
  `PatientID` int NOT NULL AUTO_INCREMENT,
  `ProjectID` int NOT NULL,
  `BirthDate` date DEFAULT NULL,
  `Sex` enum('M','F') DEFAULT NULL,
  `PatientIdentifier` varchar(255) NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`PatientID`),
  UNIQUE KEY `ProjectIDPatientIdentifier_UNIQUE` (`ProjectID`,`PatientIdentifier`),
  KEY `fk_Patient_Project1_idx` (`ProjectID`),
  KEY `ix_Patient_Project_Sex_BirthDate` (`ProjectID`,`Sex`,`BirthDate`),
  KEY `ix_Patient_PatientIdentifier` (`PatientIdentifier`),
  CONSTRAINT `Patient_ibfk_1` FOREIGN KEY (`ProjectID`) REFERENCES `Project` (`ProjectID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Project` (
  `ProjectID` int NOT NULL AUTO_INCREMENT,
  `ProjectName` varchar(255) NOT NULL,
  `External` enum('Y','N','M') NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Description` text,
  `ContactID` int DEFAULT NULL,
  `DOI` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`ProjectID`),
  UNIQUE KEY `ProjectName_UNIQUE` (`ProjectName`),
  KEY `fk_Project_Contact1_idx` (`ContactID`),
  CONSTRAINT `fk_Project_Contact1` FOREIGN KEY (`ContactID`) REFERENCES `Contact` (`ContactID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Scan` (
  `ScanID` int NOT NULL AUTO_INCREMENT,
  `ScanMode` varchar(40) NOT NULL,
  PRIMARY KEY (`ScanID`),
  UNIQUE KEY `ScanMode_UNIQUE` (`ScanMode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Segmentation` (
  `SegmentationID` int NOT NULL AUTO_INCREMENT,
  `ImageInstanceID` int NOT NULL,
  `ZarrArrayIndex` int DEFAULT NULL,
  `CreatorID` int NOT NULL,
  `FeatureID` int NOT NULL,
  `SubTaskID` int DEFAULT NULL,
  `DataRepresentation` enum('Binary','DualBitMask','Probability','MultiLabel','MultiClass') NOT NULL,
  `DataType` enum('R8','R8UI','R16UI','R32UI','R32F') NOT NULL,
  `ScanIndices` json DEFAULT NULL,
  `SparseAxis` int DEFAULT NULL,
  `Depth` int NOT NULL,
  `Height` int NOT NULL,
  `Width` int NOT NULL,
  `ImageProjectionMatrix` json DEFAULT NULL,
  `Threshold` float DEFAULT NULL,
  `ReferenceSegmentationID` int DEFAULT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `DateModified` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `Inactive` tinyint(1) NOT NULL,
  PRIMARY KEY (`SegmentationID`),
  KEY `CreatorID` (`CreatorID`),
  KEY `ReferenceSegmentationID` (`ReferenceSegmentationID`),
  KEY `ix_Segmentation_Feature_Inactive` (`FeatureID`,`Inactive`),
  KEY `ix_Segmentation_Image_Feature_Inactive` (`ImageInstanceID`,`FeatureID`,`Inactive`),
  KEY `ix_Segmentation_SubTask_Feature` (`SubTaskID`,`FeatureID`),
  CONSTRAINT `Segmentation_ibfk_1` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `Segmentation_ibfk_2` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `Segmentation_ibfk_3` FOREIGN KEY (`FeatureID`) REFERENCES `Feature` (`FeatureID`),
  CONSTRAINT `Segmentation_ibfk_4` FOREIGN KEY (`ReferenceSegmentationID`) REFERENCES `Segmentation` (`SegmentationID`),
  CONSTRAINT `Segmentation_ibfk_5` FOREIGN KEY (`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `SegmentationModel` (
  `ModelID` int NOT NULL,
  `FeatureID` int DEFAULT NULL,
  PRIMARY KEY (`ModelID`),
  KEY `FeatureID` (`FeatureID`),
  CONSTRAINT `SegmentationModel_ibfk_1` FOREIGN KEY (`FeatureID`) REFERENCES `Feature` (`FeatureID`),
  CONSTRAINT `SegmentationModel_ibfk_2` FOREIGN KEY (`ModelID`) REFERENCES `Model` (`ModelID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `SegmentationTag` (
  `TagID` int NOT NULL,
  `SegmentationID` int NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Comment` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`TagID`,`SegmentationID`),
  KEY `fk_SegmentationTag_Segmentation1_idx` (`SegmentationID`),
  KEY `fk_SegmentationTag_Tag1_idx` (`TagID`),
  KEY `fk_SegmentationTag_Creator1_idx` (`CreatorID`),
  KEY `ix_SegmentationTag_Segmentation_Tag` (`SegmentationID`,`TagID`),
  CONSTRAINT `SegmentationTag_ibfk_3` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `SegmentationTag_ibfk_4` FOREIGN KEY (`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE,
  CONSTRAINT `SegmentationTag_ibfk_5` FOREIGN KEY (`SegmentationID`) REFERENCES `Segmentation` (`SegmentationID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Series` (
  `SeriesID` int NOT NULL AUTO_INCREMENT,
  `StudyID` int NOT NULL,
  `SeriesNumber` int DEFAULT NULL,
  `SeriesInstanceUid` varchar(64) DEFAULT NULL,
  `StudyInstanceUid` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`SeriesID`),
  UNIQUE KEY `SeriesInstanceUid_UNIQUE` (`SeriesInstanceUid`),
  UNIQUE KEY `StudyInstanceUidSeriesInstanceUid_UNIQUE` (`StudyInstanceUid`,`SeriesInstanceUid`),
  KEY `fk_Series_Study1_idx` (`StudyID`),
  KEY `ix_Series_StudyID_SeriesNumber` (`StudyID`,`SeriesNumber`),
  KEY `ix_Series_StudyID_StudyInstanceUid` (`StudyID`,`StudyInstanceUid`),
  CONSTRAINT `Series_ibfk_1` FOREIGN KEY (`StudyID`) REFERENCES `Study` (`StudyID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `SourceInfo` (
  `SourceInfoID` int NOT NULL AUTO_INCREMENT,
  `SourcePath` varchar(250) NOT NULL,
  `SourceName` varchar(64) NOT NULL,
  `ThumbnailPath` varchar(250) DEFAULT NULL,
  PRIMARY KEY (`SourceInfoID`),
  UNIQUE KEY `SourceName_UNIQUE` (`SourceName`),
  UNIQUE KEY `SourcePath_UNIQUE` (`SourcePath`),
  UNIQUE KEY `ThumbnailPath_UNIQUE` (`ThumbnailPath`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `StorageBackend` (
  `StorageBackendID` int NOT NULL AUTO_INCREMENT,
  `Key` varchar(256) NOT NULL,
  `Kind` varchar(256) NOT NULL,
  `Config` json DEFAULT NULL,
  PRIMARY KEY (`StorageBackendID`),
  UNIQUE KEY `uq_StorageBackend_Key` (`Key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Study` (
  `StudyID` int NOT NULL AUTO_INCREMENT,
  `PatientID` int NOT NULL,
  `StudyDescription` varchar(64) DEFAULT NULL,
  `StudyDate` date NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `StudyRound` int DEFAULT NULL,
  PRIMARY KEY (`StudyID`),
  UNIQUE KEY `PatientIDStudyDate_UNIQUE` (`PatientID`,`StudyDate`),
  KEY `fk_Study_Patient1_idx` (`PatientID`),
  KEY `StudyRound` (`StudyRound`),
  KEY `StudyDate_idx` (`StudyDate`),
  KEY `ix_Study_PatientID_StudyRound` (`PatientID`,`StudyRound`),
  KEY `ix_Study_StudyRound_StudyDate` (`StudyRound`,`StudyDate`),
  CONSTRAINT `Study_ibfk_1` FOREIGN KEY (`PatientID`) REFERENCES `Patient` (`PatientID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `StudyTag` (
  `StudyID` int NOT NULL,
  `TagID` int NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Comment` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`StudyID`,`TagID`),
  KEY `fk_StudyTag_Study1_idx` (`StudyID`),
  KEY `fk_StudyTag_Tag1_idx` (`TagID`),
  KEY `fk_StudyTag_Creator1_idx` (`CreatorID`),
  KEY `ix_StudyTag_Study_Tag` (`StudyID`,`TagID`),
  CONSTRAINT `StudyTag_ibfk_1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `StudyTag_ibfk_2` FOREIGN KEY (`TagID`) REFERENCES `Tag` (`TagID`) ON DELETE CASCADE,
  CONSTRAINT `StudyTag_ibfk_3` FOREIGN KEY (`StudyID`) REFERENCES `Study` (`StudyID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `SubTask` (
  `SubTaskID` int NOT NULL AUTO_INCREMENT,
  `TaskID` int NOT NULL,
  `CreatorID` int DEFAULT NULL,
  `Comments` text,
  `TaskState` enum('NotStarted','Busy','Ready') NOT NULL,
  PRIMARY KEY (`SubTaskID`),
  KEY `fk_SubTask_Creator1_idx` (`CreatorID`),
  KEY `fk_SubTask_Task1_idx` (`TaskID`),
  KEY `ix_SubTask_TaskState_Creator` (`TaskState`,`CreatorID`),
  CONSTRAINT `fk_SubTask_Creator1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`),
  CONSTRAINT `SubTask_ibfk_1` FOREIGN KEY (`TaskID`) REFERENCES `Task` (`TaskID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `SubTaskImageLink` (
  `ImageInstanceID` int NOT NULL,
  `SubTaskID` int NOT NULL,
  `ImageIndex` int NOT NULL,
  UNIQUE KEY `uq_SubTaskImageLink_SubTask_ImageIndex` (`SubTaskID`,`ImageIndex`),
  KEY `fk_SubTaskImageLink_ImageInstance1_idx` (`ImageInstanceID`),
  KEY `fk_SubTaskImageLink_SubTask1_idx` (`SubTaskID`),
  KEY `ix_SubTaskImageLink_Image_SubTask` (`ImageInstanceID`,`SubTaskID`),
  CONSTRAINT `SubTaskImageLink_ibfk_1` FOREIGN KEY (`ImageInstanceID`) REFERENCES `ImageInstance` (`ImageInstanceID`) ON DELETE CASCADE,
  CONSTRAINT `SubTaskImageLink_ibfk_2` FOREIGN KEY (`SubTaskID`) REFERENCES `SubTask` (`SubTaskID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Tag` (
  `TagID` int NOT NULL AUTO_INCREMENT,
  `TagName` varchar(256) NOT NULL,
  `TagType` enum('Study','ImageInstance','Annotation','Segmentation','FormAnnotation') NOT NULL,
  `TagDescription` varchar(256) NOT NULL,
  `CreatorID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`TagID`),
  UNIQUE KEY `Tag` (`TagName`,`TagType`),
  KEY `fk_Tag_Creator1_idx` (`CreatorID`),
  CONSTRAINT `Tag_ibfk_1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Task` (
  `TaskID` int NOT NULL AUTO_INCREMENT,
  `TaskName` varchar(256) NOT NULL,
  `TaskDefinitionID` int NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Description` text,
  `ContactID` int DEFAULT NULL,
  `CreatorID` int DEFAULT NULL,
  `TaskState` enum('NotStarted','Busy','Finished','Aborted','Archived') NOT NULL,
  PRIMARY KEY (`TaskID`),
  KEY `fk_Task_TaskDefinition1_idx` (`TaskDefinitionID`),
  KEY `fk_Task_Contact1` (`ContactID`),
  KEY `ix_Task_Creator_TaskDefinition` (`CreatorID`,`TaskDefinitionID`),
  CONSTRAINT `fk_Task_Contact1` FOREIGN KEY (`ContactID`) REFERENCES `Contact` (`ContactID`),
  CONSTRAINT `fk_Task_TaskDefinition1` FOREIGN KEY (`TaskDefinitionID`) REFERENCES `TaskDefinition` (`TaskDefinitionID`),
  CONSTRAINT `Task_ibfk_1` FOREIGN KEY (`CreatorID`) REFERENCES `Creator` (`CreatorID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `TaskDefinition` (
  `TaskDefinitionID` int NOT NULL AUTO_INCREMENT,
  `TaskDefinitionName` varchar(256) NOT NULL,
  `DateInserted` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `TaskConfig` json DEFAULT NULL,
  PRIMARY KEY (`TaskDefinitionID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('a1d1700000a1');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

