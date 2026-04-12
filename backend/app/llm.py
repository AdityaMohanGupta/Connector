import google.generativeai as genai
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models import ChatMessage, User
from app.agent import AgentService, TOOLS_METADATA
import json
from typing import Any

class LLMService:
    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment.")
        genai.configure(api_key=settings.gemini_api_key)
        # We define tools for the model. Note: In a production app, 
        # you'd map these strings to actual functions.
        self.model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=TOOLS_METADATA
        )

    async def get_history(self, db: AsyncSession, user_id: str, limit: int = 15):
        result = await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = list(result)
        messages.reverse()
        return messages

    async def chat(self, db: AsyncSession, user: User, user_message: str):
        # 1. Load history
        history = await self.get_history(db, user.id)
        
        # 2. Save user message to DB
        user_msg_db = ChatMessage(user_id=user.id, role="user", content=user_message)
        db.add(user_msg_db)
        await db.commit()

        # 3. Start Chat Session
        # Map DB roles to Gemini roles (user -> user, assistant -> model)
        chat_history = []
        for m in history:
            role = "user" if m.role == "user" else "model"
            chat_history.append({"role": role, "parts": [m.content]})
            
        chat = self.model.start_chat(history=chat_history)
        
        # 4. Send message and handle tool calls
        response = chat.send_message(user_message)
        
        # Handle possible function calls in a loop (recursive tool use)
        # For simplicity in this version, we handle one level of tool calling.
        agent = AgentService()
        
        while response.candidates[0].content.parts[0].function_call:
            call = response.candidates[0].content.parts[0].function_call
            tool_name = call.name
            # Convert proto arguments to standard Python types for JSON serialization
            arguments = {}
            for k, v in call.args.items():
                if hasattr(v, "__iter__") and not isinstance(v, (str, dict)):
                    arguments[k] = list(v)
                else:
                    arguments[k] = v
            
            # Invoke the tool through AgentService
            tool_result = await agent.invoke_tool(db, user, tool_name, arguments)
            
            # Send result back to Gemini
            response = chat.send_message(
                genai.protos.Content(
                parts=[genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={'result': json.dumps(tool_result)}
                    )
                )]
            ))

        assistant_content = response.text
        
        # 5. Save assistant message to DB
        assistant_msg_db = ChatMessage(user_id=user.id, role="assistant", content=assistant_content)
        db.add(assistant_msg_db)
        await db.commit()
        await db.refresh(assistant_msg_db)
        
        return assistant_msg_db
