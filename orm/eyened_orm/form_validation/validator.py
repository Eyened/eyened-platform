"""Form validation module for eyened_orm."""

from typing import Dict, List, Tuple, Optional
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from jsonschema import validate, ValidationError, Draft7Validator, SchemaError

from ..form_annotation import FormAnnotation, FormSchema
from ..db import DBManager


def validate_form(form_annotation: FormAnnotation) -> Tuple[bool, List[str]]:
    """
    Validate a single FormAnnotation against its schema.
    
    Args:
        form_annotation: The FormAnnotation instance to validate
        
    Returns:
        Tuple containing:
            - Boolean indicating if validation passed
            - List of error messages (empty if validation passed)
    """
    # Skip if no FormData or Schema
    if not form_annotation.FormData or not form_annotation.FormSchema.Schema:
        return False, ["Missing form data or schema"]
    
    errors = []
    is_valid = True
    
    try:
        validate(instance=form_annotation.FormData, schema=form_annotation.FormSchema.Schema)
    except ValidationError as e:
        is_valid = False
        # Add the validation error message
        errors.append(str(e))
    
    return is_valid, errors


def validate_all_forms(session: Optional[Session] = None, print_errors: bool = False) -> pd.DataFrame:
    """
    Validate all FormAnnotation instances in the database.
    
    Args:
        session: SQLAlchemy session to use. If None, a new session will be created.
        print_errors: If True, print errors encountered during validation.
        
    Returns:
        DataFrame with validation statistics.
    """
    if session is None:
        session = DBManager.get_session()
    
    # Query all active form annotations
    query = select(FormAnnotation).where(~FormAnnotation.Inactive)
    form_annotations = session.execute(query).scalars().all()
    
    # Track validation results
    results = []
    
    for form in form_annotations:
        schema_name = form.FormSchema.SchemaName if form.FormSchema else "Unknown"
        is_valid, errors = validate_form(form)
        
        result = {
            "FormAnnotationID": form.FormAnnotationID,
            "SchemaName": schema_name,
            "IsValid": is_valid,
            "ErrorCount": len(errors)
        }
        
        results.append(result)
        
        if print_errors and errors:
            print(f"FormAnnotationID: {form.FormAnnotationID} (Schema: {schema_name})")
            for error in errors:
                print(f"  - {error}")
    
    # Create dataframe with results
    results_df = pd.DataFrame(results)
    
    # Generate summary statistics
    if not results_df.empty:
        total = len(results_df)
        valid = results_df["IsValid"].sum()
        invalid = total - valid
        
        stats_df = pd.DataFrame({
            "Metric": ["Total Forms", "Valid Forms", "Invalid Forms", "Validity Percentage"],
            "Value": [total, valid, invalid, f"{(valid/total)*100:.2f}%"]
        })
        
        # Group by schema name to see error distribution
        schema_stats = results_df.groupby("SchemaName").agg(
            TotalForms=("FormAnnotationID", "count"),
            ValidForms=("IsValid", "sum")
        )
        
        schema_stats["InvalidForms"] = schema_stats["TotalForms"] - schema_stats["ValidForms"]
        schema_stats["ValidityPercentage"] = (schema_stats["ValidForms"] / schema_stats["TotalForms"] * 100).round(2).astype(str) + "%"
        schema_stats = schema_stats.reset_index()
        
        if print_errors:
            print("\nValidation Summary:")
            print(f"Total Forms: {total}")
            print(f"Valid Forms: {valid}")
            print(f"Invalid Forms: {invalid}")
            print(f"Validity Percentage: {(valid/total)*100:.2f}%")
            
            print("\nValidation by Schema:")
            print(schema_stats.to_string(index=False))
        
        return schema_stats
    
    return pd.DataFrame()


def validate_all_schemas(session: Optional[Session] = None, print_errors: bool = False) -> pd.DataFrame:
    """
    Validate all FormSchema instances in the database to ensure they are valid JSON Schema definitions.
    
    Args:
        session: SQLAlchemy session to use. If None, a new session will be created.
        print_errors: If True, print errors encountered during validation.
        
    Returns:
        DataFrame with validation statistics.
    """
    if session is None:
        session = DBManager.get_session()
    
    # Query all form schemas
    query = select(FormSchema)
    form_schemas = session.execute(query).scalars().all()
    
    # Track validation results
    results = []
    
    for schema in form_schemas:
        is_valid = True
        errors = []
        
        if not schema.Schema:
            is_valid = False
            errors.append("Missing schema definition")
        else:
            try:
                # Validate the schema itself against JSON Schema meta-schema
                Draft7Validator.check_schema(schema.Schema)
            except SchemaError as e:
                is_valid = False
                errors.append(str(e))
            except Exception as e:
                is_valid = False
                errors.append(f"Unexpected error: {str(e)}")
        
        result = {
            "FormSchemaID": schema.FormSchemaID,
            "SchemaName": schema.SchemaName if schema.SchemaName else "Unknown",
            "IsValid": is_valid,
            "ErrorCount": len(errors)
        }
        
        results.append(result)
        
        if print_errors and errors:
            print(f"FormSchemaID: {schema.FormSchemaID} (Name: {schema.SchemaName})")
            for error in errors:
                print(f"  - {error}")
    
    # Create dataframe with results
    results_df = pd.DataFrame(results)
    
    # Generate summary statistics
    if not results_df.empty:
        total = len(results_df)
        valid = results_df["IsValid"].sum()
        invalid = total - valid
        
        schema_stats = pd.DataFrame({
            "Metric": ["Total Schemas", "Valid Schemas", "Invalid Schemas", "Validity Percentage"],
            "Value": [total, valid, invalid, f"{(valid/total)*100:.2f}%"]
        })
        
        if print_errors:
            print("\nSchema Validation Summary:")
            print(f"Total Schemas: {total}")
            print(f"Valid Schemas: {valid}")
            print(f"Invalid Schemas: {invalid}")
            print(f"Validity Percentage: {(valid/total)*100:.2f}%")
        
        return schema_stats
    
    return pd.DataFrame()


def validate_all(session: Optional[Session] = None, print_errors: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Run both form and schema validation and return combined results.
    
    Args:
        session: SQLAlchemy session to use. If None, a new session will be created.
        print_errors: If True, print errors encountered during validation.
        
    Returns:
        Dictionary with validation results DataFrames:
            - 'schemas': Schema validation results
            - 'forms': Form validation results
    """
    if session is None:
        session = DBManager.get_session()
    
    if print_errors:
        print("=== VALIDATING FORM SCHEMAS ===")
    
    # First validate schemas
    schema_stats = validate_all_schemas(session, print_errors)
    
    if print_errors:
        print("\n=== VALIDATING FORM CONTENTS ===")
    
    # Then validate forms
    form_stats = validate_all_forms(session, print_errors)
    
    return {
        'schemas': schema_stats,
        'forms': form_stats
    } 