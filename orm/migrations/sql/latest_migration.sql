-- Running upgrade 62b55e9c9e70 -> 5ffd55a02beb

DROP INDEX `ix_FormAnnotation_FormAnnotationReferenceID` ON `FormAnnotation`;

ALTER TABLE `ImageInstance` ADD COLUMN `AltDatasetIdentifier` VARCHAR(256);

ALTER TABLE `ImageInstance` MODIFY `Laterality` ENUM('L','R') NOT NULL;

ALTER TABLE `Series` ADD COLUMN `StudyInstanceUid` VARCHAR(64);

CREATE UNIQUE INDEX `StudyInstanceUidSeriesInstanceUid_UNIQUE` ON `Series` (`StudyInstanceUid`, `SeriesInstanceUid`);

DROP INDEX `StudyInstanceUid_UNIQUE` ON `Study`;

ALTER TABLE `Study` DROP COLUMN `StudyInstanceUid`;

UPDATE alembic_version SET version_num='5ffd55a02beb' WHERE alembic_version.version_num = '62b55e9c9e70';

