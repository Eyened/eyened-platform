-- Running upgrade 832ed384515f -> fb4e76de3be8

ALTER TABLE `Annotation` ADD CONSTRAINT `fk_Annotation_Annotation1` FOREIGN KEY(`AnnotationReferenceID`) REFERENCES `Annotation` (`AnnotationID`);

ALTER TABLE `ImageInstance` MODIFY `FileChecksum` BLOB(16) NULL;

ALTER TABLE `ImageInstance` MODIFY `DataHash` BLOB(32) NULL;

CREATE INDEX `StudyDate_idx` ON `Study` (`StudyDate`);

UPDATE alembic_version SET version_num='fb4e76de3be8' WHERE alembic_version.version_num = '832ed384515f';

