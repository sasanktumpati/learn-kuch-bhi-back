from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    chat_id: str = Field(..., description="Unique identifier for the chat")
    id: str = Field(..., description="Unique identifier for the message, sequential")
    message_type: str = Field(
        ..., description="Type of the message. Either user or system"
    )
    content: str = Field(..., description="Content of the message")
    timestamp: str = Field(..., description="Timestamp of the message")


class Chat(BaseModel):
    id: str = Field(..., description="Unique identifier for the chat")
    messages: list[ChatMessage] = Field(..., description="List of messages in the chat")


class ChatAttachment(BaseModel):
    id: str = Field(..., description="Unique identifier for the attachment")
    chat_id: str = Field(..., description="Unique identifier for the chat")
    message_id: str = Field(..., description="Unique identifier for the message")
    type: str = Field(..., description="Type of the attachment")
    path: str = Field(..., description="Path of the attachment on the server")
    timestamp: str = Field(..., description="Timestamp of the attachment")
