# Chatbot Integration Setup Guide

## Overview
This guide explains how to set up the AI chatbot integration in your stress management system.

## Prerequisites
1. A GROQ API key (sign up at https://console.groq.com/)
2. Python packages: `langchain` and `langchain-groq`

## Environment Variables
Add the following to your `.env` file:
```
GROQ_API_KEY=your-groq-api-key-here
```

## Installation Steps

### 1. Install Dependencies
```bash
pip install langchain langchain-groq
```

### 2. Database Migration
Run the database migration to create chat tables:
```bash
cd backend
alembic upgrade head
```

### 3. Start the Backend
```bash
cd backend
uvicorn main:app --reload
```

### 4. Start the Frontend
```bash
cd frontend
npm run dev
```

## Features
- **Persistent Chat Sessions**: All conversations are saved to the database
- **User Authentication**: Chat sessions are tied to authenticated users
- **Chat History**: Users can view and continue previous conversations
- **AI-Powered Responses**: Uses GROQ's LLM for intelligent stress management advice

## API Endpoints
- `POST /chatbot/chat` - Send a message and get AI response
- `GET /chatbot/sessions` - Get user's chat sessions
- `GET /chatbot/sessions/{session_id}/messages` - Get messages for a session
- `DELETE /chatbot/sessions/{session_id}` - Delete a chat session

## Usage
1. Navigate to the AI Chat page in your application
2. Start a new conversation or continue an existing one
3. Type your message and receive AI-powered wellness advice
4. View your chat history in the sidebar

## Customization
- Modify the system prompt in `chatbot.py` to change the AI's behavior
- Adjust the LLM model in the Chatbot class
- Customize the UI styling in `AiChat.jsx` 