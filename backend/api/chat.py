"""
Chat API Endpoints
Handles chat interactions with conversation management and context retention
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import asyncio
import traceback
import logging

from services.conversation_manager import conversation_manager, MessageRole
from core.simple_rag import rag_pipeline
from services.enhanced_rag_service import enhanced_rag_service
# from core.hallucination_detector import hallucination_detector
from utils.monitoring import log_query_metrics
from utils.exceptions import LegalAIException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Request/Response Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None
    citations: Optional[List[Dict]] = None
    processing_time: Optional[float] = None

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message", min_length=1, max_length=10000)
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    mode: str = Field("qa", description="Chat mode: qa, drafting, or summarization")
    user_id: str = Field("demo_user", description="User identifier")
    include_context: bool = Field(True, description="Include conversation context")
    max_context_messages: int = Field(10, description="Maximum context messages")

class ChatResponse(BaseModel):
    message_id: str
    conversation_id: str
    response: str
    citations: List[Dict] = []
    processing_time: float
    token_usage: Dict[str, int] = {}
    context_used: bool = False
    conversation_title: Optional[str] = None

class ConversationListResponse(BaseModel):
    conversations: List[Dict[str, Any]]
    total_count: int
    has_more: bool

class UpdateTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="New conversation title")

class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    title: str
    messages: List[ChatMessage]
    total_messages: int
    created_at: datetime
    updated_at: datetime


async def _process_chat_request(
    request: ChatRequest,
    background_tasks: BackgroundTasks
) -> ChatResponse:
    """Shared handler for chat endpoints."""
    start_time = datetime.now()

    # Create or get conversation
    if not request.conversation_id:
        conversation = await conversation_manager.create_conversation(
            user_id=request.user_id,
            title=None  # Auto-generated later
        )
        conversation_id = conversation.id
    else:
        conversation_id = request.conversation_id

    # Persist user message
    await conversation_manager.add_message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=request.message,
        metadata={"mode": request.mode}
    )

    # Gather context if requested
    context_messages: List = []
    if request.include_context:
        context_messages = await conversation_manager.get_conversation_context(conversation_id)

    # Run Enhanced RAG pipeline (with web search if enabled)
    rag_response = await enhanced_rag_service.process_query(
        query=request.message,
        user_id=request.user_id,
        mode=request.mode,
        conversation_context=context_messages[-request.max_context_messages:] if context_messages else []
    )

    # Simplified for local development
    final_response = rag_response.answer
    final_citations = rag_response.citations
    processing_time = (datetime.now() - start_time).total_seconds()

    assistant_message = await conversation_manager.add_message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=final_response,
        citations=final_citations,
        processing_time=processing_time,
        token_usage=rag_response.token_usage,
        metadata={
            "mode": request.mode,
            "confidence_score": rag_response.confidence_score
        }
    )

    conversation_title = None
    if len(context_messages) <= 2:
        conversation_title = await conversation_manager.auto_generate_title(conversation_id)
        await conversation_manager.update_conversation_title(conversation_id, conversation_title)

    background_tasks.add_task(
        log_query_metrics,
        query=request.message,
        response=final_response,
        processing_time=processing_time,
        user_id=request.user_id,
        conversation_id=conversation_id,
        mode=request.mode
    )

    return ChatResponse(
        message_id=assistant_message.id,
        conversation_id=conversation_id,
        response=final_response,
        citations=final_citations,
        processing_time=processing_time,
        token_usage=rag_response.token_usage,
        context_used=len(context_messages) > 0,
        conversation_title=conversation_title
    )

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """
    Send a message and get AI response with full conversation context
    """
    try:
        return await _process_chat_request(request, background_tasks)
    except HTTPException:
        raise
    except LegalAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.post("/query", response_model=ChatResponse)
async def query_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """Alias endpoint used by the web UI (ChatGPT-style)."""
    try:
        return await _process_chat_request(request, background_tasks)
    except HTTPException:
        raise
    except LegalAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    user_id: str = "demo_user",
    limit: int = 20,
    offset: int = 0
):
    """
    Get user's conversation list with pagination
    """
    try:
        conversations = await conversation_manager.get_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        # Get total count for pagination
        total_count = len(conversations)  # Simplified for demo
        has_more = len(conversations) == limit
        
        # Convert to response format
        conversation_list = []
        for conv in conversations:
            # Get last message preview
            messages = await conversation_manager.get_conversation_history(conv.id, 1)
            last_message = messages[-1] if messages else None
            
            conversation_list.append({
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "message_count": conv.message_count,
                "last_message_preview": last_message.content[:100] + "..." if last_message and len(last_message.content) > 100 else last_message.content if last_message else "",
                "status": conv.status.value
            })
        
        return ConversationListResponse(
            conversations=conversation_list,
            total_count=total_count,
            has_more=has_more
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversations: {str(e)}"
        )

@router.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    limit: int = 50
):
    """
    Get full conversation history
    """
    try:
        # Get conversation details
        summary = await conversation_manager.get_conversation_summary(conversation_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get messages
        messages = await conversation_manager.get_conversation_history(conversation_id, limit)
        
        # Convert messages to response format
        chat_messages = []
        for msg in messages:
            chat_messages.append(ChatMessage(
                role=msg.role.value,
                content=msg.content,
                timestamp=msg.timestamp,
                citations=msg.citations,
                processing_time=msg.processing_time
            ))
        
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            title=summary["title"],
            messages=chat_messages,
            total_messages=summary["actual_message_count"],
            created_at=datetime.fromisoformat(summary["created_at"]),
            updated_at=datetime.fromisoformat(summary["updated_at"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversation history: {str(e)}"
        )

@router.post("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    request: UpdateTitleRequest
):
    """
    Update conversation title
    """
    try:
        success = await conversation_manager.update_conversation_title(conversation_id, request.title)

        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Title updated successfully", "title": request.title}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating title: {str(e)}"
        )

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete (archive) a conversation
    """
    try:
        success = await conversation_manager.delete_conversation(conversation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting conversation: {str(e)}"
        )

@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(conversation_id: str):
    """
    Archive a conversation
    """
    try:
        success = await conversation_manager.archive_conversation(conversation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"message": "Conversation archived successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error archiving conversation: {str(e)}"
        )

@router.get("/conversations/search")
async def search_conversations(
    user_id: str = Query("demo_user"),
    query: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Search conversations by content
    """
    try:
        results = await conversation_manager.search_conversations(
            user_id=user_id,
            query=query,
            limit=limit
        )

        return {
            "query": query,
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching conversations: {str(e)}"
        )

@router.get("/conversations/{conversation_id}/summary")
async def get_conversation_summary(conversation_id: str):
    """
    Get conversation summary and statistics
    """
    try:
        summary = await conversation_manager.get_conversation_summary(conversation_id)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving conversation summary: {str(e)}"
        )

@router.post("/conversations/new")
async def create_new_conversation(
    user_id: str = "demo_user",
    title: Optional[str] = None
):
    """
    Create a new conversation
    """
    try:
        conversation = await conversation_manager.create_conversation(
            user_id=user_id,
            title=title
        )
        
        return {
            "conversation_id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating conversation: {str(e)}"
        )
