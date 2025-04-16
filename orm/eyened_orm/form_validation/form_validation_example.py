#!/usr/bin/env python
"""
Example script demonstrating the usage of the eyened_orm.forms subpackage.
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import eyened_orm
from eyened_orm import DBManager
from eyened_orm.FormAnnotation import FormSchema, FormAnnotation
from eyened_orm.forms import (
    validate_form,
    get_schema,
    list_schemas,
    get_form_schemas,
    get_form_annotations,
    import_schema_to_db,
    load_schema_from_file,
)


def main():
    parser = argparse.ArgumentParser(description="Form validation example")
    parser.add_argument(
        "--config", help="Path to config file", default="eyened_orm/config.py"
    )
    parser.add_argument(
        "--schema-file", help="Path to JSON schema file to import", default=None
    )
    parser.add_argument(
        "--validate-annotation",
        help="ID of form annotation to validate",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--list-schemas", help="List available schemas", action="store_true"
    )
    parser.add_argument(
        "--list-annotations",
        help="List form annotations for a schema",
        default=None,
        metavar="SCHEMA_NAME",
    )
    args = parser.parse_args()

    # Initialize database connection
    dbm = DBManager(args.config)
    session = dbm.get_session()

    try:
        if args.schema_file:
            # Import a JSON schema from file
            schema_path = Path(args.schema_file)
            if not schema_path.exists():
                print(f"Schema file not found: {args.schema_file}")
                return 1

            try:
                schema_data = load_schema_from_file(str(schema_path))
                schema_name = schema_data.get("title", schema_path.stem)
                
                form_schema = import_schema_to_db(
                    session=session,
                    schema_data=schema_data,
                    schema_name=schema_name
                )
                
                print(f"Successfully imported schema: {schema_name} (ID: {form_schema.FormSchemaID})")
                
            except Exception as e:
                print(f"Error importing schema: {str(e)}")
                return 1

        if args.list_schemas:
            # List available schemas
            schemas = get_form_schemas(session)
            
            if not schemas:
                print("No schemas found in the database")
                return 0
                
            print("\nAvailable Form Schemas:")
            print("-----------------------")
            for schema in schemas:
                print(f"ID: {schema.FormSchemaID}, Name: {schema.SchemaName}")
                
                # Show some basic information about the schema
                if schema.Schema and isinstance(schema.Schema, dict):
                    property_count = len(schema.Schema.get("properties", {}))
                    required_fields = schema.Schema.get("required", [])
                    print(f"  Properties: {property_count}, Required Fields: {len(required_fields)}")

        if args.validate_annotation:
            # Validate a form annotation
            from eyened_orm.forms import check_form_submission
            
            annotation_id = args.validate_annotation
            is_valid, error_message = check_form_submission(session, annotation_id)
            
            annotation = session.execute(
                select(FormAnnotation).where(FormAnnotation.FormAnnotationID == annotation_id)
            ).scalar_one_or_none()
            
            if annotation is None:
                print(f"Form annotation not found: {annotation_id}")
                return 1
                
            schema = annotation.FormSchema
            
            print(f"\nValidating Form Annotation {annotation_id} (Schema: {schema.SchemaName})")
            print("-" * 60)
            
            if is_valid:
                print("✓ Form data is valid according to its schema")
            else:
                print(f"✗ Validation failed: {error_message}")
                
            # Print some information about the form data
            if annotation.FormData:
                print("\nForm Data:")
                print("-" * 60)
                for key, value in annotation.FormData.items():
                    print(f"{key}: {value}")

        if args.list_annotations:
            # List form annotations for a specific schema
            schema_name = args.list_annotations
            annotations = get_form_annotations(session, schema_name=schema_name)
            
            if not annotations:
                print(f"No annotations found for schema: {schema_name}")
                return 0
                
            print(f"\nForm Annotations for Schema: {schema_name}")
            print("-" * 60)
            
            for ann in annotations[:10]:  # Limit to 10 annotations for brevity
                print(f"ID: {ann.FormAnnotationID}, Creator: {ann.Creator.CreatorName}, Date: {ann.DateInserted}")
                
            if len(annotations) > 10:
                print(f"... and {len(annotations) - 10} more annotations")

        return 0

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main()) 