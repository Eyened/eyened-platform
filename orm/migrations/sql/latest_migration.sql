ALTER TABLE `ImageInstance` MODIFY `PublicID` CHAR(12) NOT NULL;

DROP INDEX `SourceInfoIDDatasetIdentifier_UNIQUE` ON `ImageInstance`;

ALTER TABLE `ImageStorage`
ADD COLUMN `DateInserted` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE `ImageStorage`
ADD COLUMN `DateModified` DATETIME
DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;


ALTER TABLE `SourceInfo` MODIFY `ThumbnailPath` VARCHAR(250) NULL;

UPDATE alembic_version SET version_num='7b36f07198ee' WHERE alembic_version.version_num = 'a231a5374a36';

