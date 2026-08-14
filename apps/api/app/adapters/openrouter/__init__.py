"""LangChain OpenRouter binding for the consultant runtime."""

from .langchain import ReceiptChatOpenRouter, build_openrouter_chat_model

__all__ = ["ReceiptChatOpenRouter", "build_openrouter_chat_model"]
