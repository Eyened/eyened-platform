Target database: root@eyened-gpu:23308/eyened_database. Proceed? [y/N] -- Running upgrade e4247389063f -> 533b4abe81b9

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

