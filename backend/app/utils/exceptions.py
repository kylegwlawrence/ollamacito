"""
Custom exception classes for the application.
"""


class OllamaException(Exception):
    """Base exception for Ollama-related errors."""

    pass


class OllamaConnectionError(OllamaException):
    """Raised when unable to connect to Ollama."""

    def __init__(self, url: str, detail: str = ""):
        self.url = url
        self.detail = detail
        super().__init__(f"Unable to connect to Ollama at {url}: {detail}")


class OllamaModelNotFoundError(OllamaException):
    """Raised when specified Ollama model is not available."""

    def __init__(self, model: str):
        self.model = model
        super().__init__(f"Ollama model '{model}' not found")


class ChatNotFoundException(Exception):
    """Raised when a chat is not found."""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        super().__init__(f"Chat with ID '{chat_id}' not found")


class MessageNotFoundException(Exception):
    """Raised when a message is not found."""

    def __init__(self, message_id: str):
        self.message_id = message_id
        super().__init__(f"Message with ID '{message_id}' not found")


class SettingsNotFoundException(Exception):
    """Raised when settings are not found."""

    def __init__(self):
        super().__init__("Settings not found")


class ValidationException(Exception):
    """Raised for validation errors."""

    def __init__(self, message: str):
        super().__init__(message)
