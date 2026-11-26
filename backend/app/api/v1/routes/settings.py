"""
Organization Settings Routes

This module contains API endpoints for managing organization settings.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import os
import shutil
import uuid
from datetime import datetime

from app.db.session import get_db, get_async_db
from app.db.models.organization import MemberRole
from app.schemas.organization import OrganizationSettingsSchema
from app.services.organization_service import OrganizationService
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException, ForbiddenException
from app.config import settings as app_settings

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get(
    "/organization/{org_id}",
    summary="Get organization settings"
)
async def get_organization_settings(
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Get the settings for a specific organization.
    
    - **org_id**: Organization ID
    """
    try:
        # Check if user has permission
        service = OrganizationService(db)
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MEMBER, MemberRole.VIEWER]
        )
        
        # Get organization
        org = await service.get_organization(org_id)
        
        # Return settings
        return {
            "settings": org.settings or {},
            "organization_id": org_id,
            "organization_name": org.name
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/organization/{org_id}",
    summary="Update organization settings"
)
async def update_organization_settings(
    settings: OrganizationSettingsSchema,
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Update the settings for a specific organization.
    
    - **org_id**: Organization ID
    - **settings**: Organization settings
    """
    try:
        # Check if user has permission
        service = OrganizationService(db)
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Update organization settings
        org = await service.update_organization(
            org_id=org_id,
            user_id=current_user.id,
            data={"settings": settings.dict(exclude_unset=True)}
        )
        
        # Return updated settings
        return {
            "settings": org.settings,
            "organization_id": org_id,
            "organization_name": org.name,
            "message": "Settings updated successfully"
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.patch(
    "/organization/{org_id}",
    summary="Update specific organization settings"
)
async def patch_organization_settings(
    updates: Dict[str, Any] = Body(..., description="Settings to update"),
    org_id: str = Path(..., description="Organization ID"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Update specific settings for an organization without replacing the entire settings object.
    
    - **org_id**: Organization ID
    - **updates**: Dictionary of settings to update
    """
    try:
        # Check if user has permission
        service = OrganizationService(db)
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Get current organization
        org = await service.get_organization(org_id)
        
        # Merge current settings with updates
        current_settings = org.settings or {}
        
        # Handle nested updates
        for key, value in updates.items():
            if isinstance(value, dict) and key in current_settings and isinstance(current_settings[key], dict):
                # Merge nested dictionaries
                current_settings[key].update(value)
            else:
                # Replace or add value
                current_settings[key] = value
        
        # Update organization settings
        org = await service.update_organization(
            org_id=org_id,
            user_id=current_user.id,
            data={"settings": current_settings}
        )
        
        # Return updated settings
        return {
            "settings": org.settings,
            "organization_id": org_id,
            "organization_name": org.name,
            "message": "Settings updated successfully"
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post(
    "/organization/{org_id}/logo",
    summary="Upload organization logo"
)
async def upload_organization_logo(
    org_id: str = Path(..., description="Organization ID"),
    logo: UploadFile = File(..., description="Logo image file"),
    db: AsyncSession = Depends(get_async_db),
    current_user = Depends(get_current_user)
):
    """
    Upload a logo for the organization.
    
    - **org_id**: Organization ID
    - **logo**: Logo image file (PNG, JPG, or SVG)
    """
    try:
        # Check if user has permission
        service = OrganizationService(db)
        await service.require_permission(
            user_id=current_user.id,
            org_id=org_id,
            required_roles=[MemberRole.OWNER, MemberRole.ADMIN]
        )
        
        # Validate file type
        allowed_extensions = [".png", ".jpg", ".jpeg", ".svg"]
        file_ext = os.path.splitext(logo.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join("uploaded_assets", "organization_logos")
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{org_id}_{timestamp}{file_ext}"
        file_path = os.path.join(uploads_dir, unique_filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        
        # Generate URL for the logo
        logo_url = f"/assets/organization_logos/{unique_filename}"
        
        # Get current organization settings
        org = await service.get_organization(org_id)
        current_settings = org.settings or {}
        
        # Update branding settings with logo URL
        if "branding" not in current_settings:
            current_settings["branding"] = {}
        
        current_settings["branding"]["logo_url"] = logo_url
        
        # Update organization settings
        org = await service.update_organization(
            org_id=org_id,
            user_id=current_user.id,
            data={"settings": current_settings}
        )
        
        # Return updated logo URL
        return {
            "logo_url": logo_url,
            "organization_id": org_id,
            "message": "Logo uploaded successfully"
        }
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ForbiddenException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
