"""
Suggested Questions Routes

API endpoints for suggested questions management:
- Get suggested questions
- Generate suggested questions
- Add/update/delete suggested questions
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.dependencies import (
    get_db, get_current_user, get_current_organization_id,
    require_permission
)
from app.services.suggested_questions_service import get_suggested_questions_service
from app.schemas.bot import (
    SuggestedQuestion, SuggestedQuestionsUpdate
)
from app.core.exceptions import (
    NotFoundException, ValidationException, ServiceException
)
from app.utils.response import create_response

router = APIRouter()


@router.get("/{bot_id}/suggested-questions")
#@require_permission("bot:view")
async def get_suggested_questions(
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:view"))
):
    """
    Get suggested questions for a bot.
    
    Requires:
    - Organization context
    - 'bot:view' permission
    """
    try:
        service = get_suggested_questions_service()
        questions = service.get_suggested_questions(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data={"questions": questions},
            message="Suggested questions retrieved successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{bot_id}/suggested-questions")
#@require_permission("bot:edit")
async def update_suggested_questions(
    questions_data: SuggestedQuestionsUpdate,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Update suggested questions for a bot.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_suggested_questions_service()
        bot = service.update_suggested_questions(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            questions_data=questions_data
        )
        
        # Get updated questions
        questions = service.get_suggested_questions(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id
        )
        
        return create_response(
            data={"questions": questions},
            message="Suggested questions updated successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{bot_id}/suggested-questions/generate")
#@require_permission("bot:edit")
async def generate_suggested_questions(
    bot_id: str = Path(..., title="Bot ID"),
    count: int = Query(5, ge=1, le=20),
    categories: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Generate suggested questions from knowledge base.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_suggested_questions_service()
        questions = await service.generate_suggested_questions(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            count=count,
            categories=categories
        )
        
        return create_response(
            data={"questions": questions},
            message=f"Generated {len(questions)} suggested questions successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{bot_id}/suggested-questions")
#@require_permission("bot:edit")
async def add_suggested_question(
    question: SuggestedQuestion,
    bot_id: str = Path(..., title="Bot ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Add a suggested question.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_suggested_questions_service()
        added_question = service.add_suggested_question(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            question=question
        )
        
        return create_response(
            data=added_question,
            message="Suggested question added successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{bot_id}/suggested-questions/{question_id}")
#@require_permission("bot:edit")
async def delete_suggested_question(
    bot_id: str = Path(..., title="Bot ID"),
    question_id: str = Path(..., title="Question ID"),
    db: Session = Depends(get_db),
    organization_id: str = Depends(get_current_organization_id),
    _ :bool= Depends(require_permission("bot:edit"))
):
    """
    Delete a suggested question.
    
    Requires:
    - Organization context
    - 'bot:edit' permission
    """
    try:
        service = get_suggested_questions_service()
        result = service.delete_suggested_question(
            db=db,
            bot_id=bot_id,
            organization_id=organization_id,
            question_id=question_id
        )
        
        return create_response(
            data=result,
            message="Suggested question deleted successfully"
        )
        
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
