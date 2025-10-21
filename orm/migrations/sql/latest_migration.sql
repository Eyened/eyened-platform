-- Running upgrade f198802eada6 -> 606596c6f965

DROP INDEX `ix_FormAnnotation_FormAnnotationReferenceID` ON `FormAnnotation`;

UPDATE alembic_version SET version_num='606596c6f965' WHERE alembic_version.version_num = 'f198802eada6';

