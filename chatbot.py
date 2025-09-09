from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferWindowMemory
from typing import Dict, List
from uuid import uuid4
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models import ChatSession, ChatMessage
from datetime import datetime

load_dotenv()

class Chatbot:
    def __init__(self, session_id: str = None):
        # Initialize your LLM (replace with your actual LLM setup)
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            max_tokens=500
        )

        self.system_prompt = """You are a helpful assistant to help the user to control his/her stress level. Your responses should be in simple English.
You are also able to use emojis in your responses. There are professional mental advisors in this system so if user is feeling lots of stress, direct the user to a professional.
**Do not provide answers to out of scope questions. If user asks out of scope questions, respond with "I'm here to help you with stress management my friend. Let's focus on that."**

## Consider these points when you are responding to the user:
- If the user is asking quick solutions to reduce the stress, give him/her quick tips.
- Always be a caring friend and a listener.
- Short answers are better than long answers.
- Avoid direct medical advice.
- Be friendly and engaging.
- Your accent should be like a friend, not a professional.

## User may have these symptoms:
- Mental & Emotional Symptoms 
- Physical Symptoms
- Work-related stress

## Give these kind of tips to the user:
- Mental & Emotional Relief Tips 
- Physical Relief Tips
- Work-related stress relief tips
- Daily Self-Care Habits 

## For Crisis Situations:
If a user expresses thoughts of self-harm or is in a severe mental health crisis, provide Emergency Mental Health Support telephone numbers and contact methods of Sri Lanka

<Examples>
### Example 1 :
    User: "Why do I feel like this?"
    Assistant : "Sometimes stress builds up quietly  
        Let's understand it together: 
        • You may be tired 
        • It's okay to feel like this 
        • You're not alone, I'm here to help "
### Example 2 :
    User: "I hate my job. What should I do?"
    Assistant : "That's hard to feel <EMOJI>
        Let's think together: 
        • What part feels the worst? 
        • Have you talked to anyone about it? 
        • Want help writing to your manager?"
### Example 3 :
    User : "I want to die because of work stress"
    Assistant : "I'm really sorry you're feeling this way  
        You are not alone. I'm here for you.
        Next Step: 
        "Please don't go through this alone. 
        Here's what we can do together: 
        • Talk to a professional consultant in this system  
        • Contact your supervisor or HR coordinator immediately"
        
### Example 4 :
    User: "I can't take this anymore, I feel like giving up."
    Assistant: "I'm really sorry you're feeling this way, my friend. You are not alone. Please know there is immediate help available.
        Here are people you can talk to right now who are here to listen and support you:
        • **Sumithrayo:** ☎️ 011 2696666
        • **CCCline:** ☎️ 1333
        • **NIMH Helpline:** ☎️ 1926

        Let's also talk to a professional consultant in this system together. I'm right here with you."  
</Examples>

# Here is the real conversation
        """
        
        self.session_id = session_id
        self.history = []
  
    def get_response(self, user_input: str, db: Session, user_id: int = None) -> str:
        """Get chatbot response for given user input"""
        
        # Add user message to history
        self.history.append({"role": "user", "content": user_input})
        
        # Save user message to database
        if self.session_id and user_id:
            user_message = ChatMessage(
                session_id=self.session_id,
                role="user",
                content=user_input,
                user_id=user_id,
                timestamp=datetime.utcnow()
            )
            db.add(user_message)
            db.commit()
        
        prompt = f"""
        {self.system_prompt}
        \n
        {self._get_history()}
        """
        
        response = self.llm.invoke(input=prompt)
        self.history.append({"role": "assistant", "content": response.content})
        
        # Save assistant message to database
        if self.session_id and user_id:
            assistant_message = ChatMessage(
                session_id=self.session_id,
                role="assistant",
                content=response.content,
                user_id=user_id,
                timestamp=datetime.utcnow()
            )
            db.add(assistant_message)
            db.commit()
        
        return response.content
    
    def _get_history(self) -> str:
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.history])
    
    def load_history_from_db(self, db: Session):
        """Load chat history from database"""
        if self.session_id:
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == self.session_id
            ).order_by(ChatMessage.timestamp).all()
            
            self.history = [
                {"role": msg.role, "content": msg.content} 
                for msg in messages
            ]

class ChatbotManager:
    def __init__(self):
        self.sessions: Dict[str, Chatbot] = {}
    
    def get_chatbot(self, session_id: str = None, user_id: int = None, db: Session = None) -> tuple[Chatbot, str]:
        if not session_id:
            session_id = str(uuid4())
            # Create new chat session in database
            if db and user_id:
                chat_session = ChatSession(
                    id=session_id,
                    user_id=user_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(chat_session)
                db.commit()
            
            self.sessions[session_id] = Chatbot(session_id)
        elif session_id not in self.sessions:
            # Load existing session from database
            if db:
                existing_session = db.query(ChatSession).filter(
                    ChatSession.id == session_id
                ).first()
                if existing_session:
                    chatbot = Chatbot(session_id)
                    chatbot.load_history_from_db(db)
                    self.sessions[session_id] = chatbot
                else:
                    raise ValueError("Invalid session ID")
            else:
                raise ValueError("Invalid session ID")
        
        return self.sessions[session_id], session_id
    
    def get_user_chat_sessions(self, user_id: int, db: Session) -> List[dict]:
        """Get all chat sessions for a user"""
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.updated_at.desc()).all()
        
        return [
            {
                "id": session.id,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "message_count": db.query(ChatMessage).filter(
                    ChatMessage.session_id == session.id
                ).count()
            }
            for session in sessions
        ]
    
    def get_chat_messages(self, session_id: str, db: Session) -> List[dict]:
        """Get all messages for a chat session"""
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.timestamp).all()
        
        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in messages
        ] 