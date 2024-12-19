from fastapi import APIRouter
from core.config import settings
import os
from src.chatbot_router import router as chat_router


api_v1_router = APIRouter(prefix=settings.API_V1_STR)

api_v1_router.include_router(chat_router)
