from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from dependencies import get_db
from auth import get_current_user
from models import User
from chatbot import ChatbotManager
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# Initialize chatbot manager
chatbot_manager = ChatbotManager()

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

class ChatSessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int

class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message to the chatbot and get a response"""
    try:
        chatbot, session_id = chatbot_manager.get_chatbot(
            session_id=request.session_id,
            user_id=current_user.id,
            db=db
        )
        
        response = chatbot.get_response(
            user_input=request.message,
            db=db,
            user_id=current_user.id
        )
        
        return ChatResponse(
            response=response,
            session_id=session_id
        )
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_user_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chat sessions for the current user"""
    try:
        sessions = chatbot_manager.get_user_chat_sessions(
            user_id=current_user.id,
            db=db
        )
        return sessions
    except Exception as e:
        print(f"Error getting chat sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages for a specific chat session"""
    try:
        # Verify the session belongs to the current user
        from models import ChatSession
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        messages = chatbot_manager.get_chat_messages(
            session_id=session_id,
            db=db
        )
        return messages
    except Exception as e:
        print(f"Error getting chat messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat session and all its messages"""
    try:
        from models import ChatSession, ChatMessage
        
        # Verify the session belongs to the current user
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Delete all messages first (due to cascade)
        db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).delete()
        
        # Delete the session
        db.delete(session)
        db.commit()
        
        # Remove from chatbot manager if it exists
        if session_id in chatbot_manager.sessions:
            del chatbot_manager.sessions[session_id]
        
        return {"message": "Chat session deleted successfully"}
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 