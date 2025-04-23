from typing import Dict, List, Optional, Any
import traceback
import importlib.util

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from eyened_orm.importer.importer import Importer
from ..db import get_db
from ..config import settings

router = APIRouter()
security = HTTPBasic()


# Pydantic models for request and response schemas
class ImportRequest(BaseModel):
    data: List[Dict[str, Any]]
    options: Dict[str, Any]

class ImportResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    background_processing: Optional[bool] = None

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify the basic HTTP authentication credentials.
    """
    correct_username = settings.admin_username
    correct_password = settings.admin_password
    
    if not correct_username or not correct_password:
        raise HTTPException(
            status_code=500,
            detail="Import API credentials not configured on the server"
        )
    
    if credentials.username != correct_username or credentials.password != correct_password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials

def make_importer(session, project_name, options: Dict[str, Any]):
    # Create importer with options
    return Importer(
        session=session,
        project_name=project_name,
        create_patients=options.get("create_patients", False),
        create_studies=options.get("create_studies", False),
        create_series=options.get("create_series", True),
        run_ai_models=options.get("run_ai_models", True),
        generate_thumbnails=options.get("generate_thumbnails", True),
        copy_files=options.get("copy_files", False),
        config={
            "images_basepath":settings.images_basepath,
            "images_basepath_container": '/images',
        }
    )

@router.post("/import/exec", response_model=ImportResponse)
async def import_exec(
    request: ImportRequest,
    session: Session = Depends(get_db),
    credentials: HTTPBasicCredentials = Depends(verify_credentials)
):
    """
    Execute the import process with the provided data and options.
    """
    try:
        # Extract options with defaults
        options = request.options or {}
        project_name = options.get("project_name")
        
        if not project_name:
            return ImportResponse(
                success=False,
                message="Import failed",
                error="project_name is required in options"
            )
        
        
        # Modify options for immediate import
        import_options = options.copy()
        # Disable AI models and thumbnail generation during import
        # These will be handled by Huey tasks
        import_options["run_ai_models"] = False
        import_options["generate_thumbnails"] = False
        
        # Create importer with modified options
        importer = make_importer(session, project_name, import_options)
        
        # Execute the import
        importer.exec(request.data)
        
        # If Huey is available, schedule background processing
        from ..utils.huey import task_run_inference, task_update_thumbnails
            
        # Schedule background processing tasks
        config = settings.make_orm_config()
        task_update_thumbnails(config)
        task_run_inference(config)
        
        return ImportResponse(
            success=True,
            message="Import completed successfully" + 
                    (" (background processing scheduled)"),
            data={"project_name": project_name}
        )
        
    except Exception as e:
        include_stack_trace = options.get("include_stack_trace", False)
        error_message = str(e)
        stack_trace = traceback.format_exc() if include_stack_trace else None
        
        return ImportResponse(
            success=False,
            message="Import failed",
            error=error_message,
            stack_trace=stack_trace
        )

@router.post("/import/summary", response_model=ImportResponse)
async def import_summary(
    request: ImportRequest,
    session: Session = Depends(get_db),
    credentials: HTTPBasicCredentials = Depends(verify_credentials)
):
    """
    Generate a summary of what would be imported with the provided data and options.
    """
    try:
        # Extract options with defaults
        options = request.options or {}
        project_name = options.get("project_name")
        
        if not project_name:
            return ImportResponse(
                success=False,
                message="Summary generation failed",
                error="project_name is required in options"
            )
        
        # Create importer with options
        importer = make_importer(session, project_name, options)
        
        # Generate the summary
        summary = importer.summary(request.data)
        
        return ImportResponse(
            success=True,
            message="Summary generated successfully",
            data=summary
        )
        
    except Exception as e:
        include_stack_trace = options.get("include_stack_trace", False)
        error_message = str(e)
        stack_trace = traceback.format_exc() if include_stack_trace else None
        
        return ImportResponse(
            success=False,
            message="Summary generation failed",
            error=error_message,
            stack_trace=stack_trace
        ) 