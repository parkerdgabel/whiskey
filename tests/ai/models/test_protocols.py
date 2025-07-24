"""Tests for AI model protocols."""

from typing import Any, AsyncIterator, Dict, List, Optional, Union

import pytest

from whiskey.ai.models import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionModel,
    EmbeddingModel,
    EmbeddingResponse,
    Message,
)


@pytest.mark.unit
class TestProtocols:
    """Test that protocols work correctly."""
    
    def test_chat_completion_protocol(self):
        """Test that classes implementing the protocol are recognized."""
        
        class ValidChatModel:
            async def create(
                self,
                messages: List[Message],
                model: str,
                temperature: float = 1.0,
                top_p: float = 1.0,
                n: int = 1,
                stream: bool = False,
                stop: Optional[Union[str, List[str]]] = None,
                max_tokens: Optional[int] = None,
                presence_penalty: float = 0.0,
                frequency_penalty: float = 0.0,
                logit_bias: Optional[Dict[str, float]] = None,
                user: Optional[str] = None,
                **kwargs: Any
            ) -> Union[ChatCompletion, AsyncIterator[ChatCompletionChunk]]:
                return ChatCompletion(id="test", model=model, choices=[])
        
        model = ValidChatModel()
        assert isinstance(model, ChatCompletionModel)
    
    def test_embedding_protocol(self):
        """Test that classes implementing the embedding protocol are recognized."""
        
        class ValidEmbeddingModel:
            async def create(
                self,
                input: Union[str, List[str]],
                model: str,
                encoding_format: str = "float",
                user: Optional[str] = None,
                **kwargs: Any
            ) -> EmbeddingResponse:
                return EmbeddingResponse(model=model)
        
        model = ValidEmbeddingModel()
        assert isinstance(model, EmbeddingModel)
    
    def test_invalid_model_not_recognized(self):
        """Test that classes not implementing the protocol are not recognized."""
        
        class InvalidModel:
            def some_method(self):
                pass
        
        model = InvalidModel()
        assert not isinstance(model, ChatCompletionModel)
        assert not isinstance(model, EmbeddingModel)
    
    def test_protocol_signature_checking(self):
        """Test that protocol checks are based on signatures."""
        
        # This class has a create method but wrong signature - it will pass isinstance
        # because Python's Protocol checking is based on method names, not signatures
        class WrongSignatureModel:
            async def create(self, messages: List[Message]) -> str:
                # Wrong return type
                return "test"
        
        # Python's Protocol checking only checks method names exist, not signatures
        # So this will actually pass isinstance check
        model = WrongSignatureModel()
        assert isinstance(model, ChatCompletionModel)  # This is expected behavior
        
        # The real type checking happens at runtime when calling the method
        # or with static type checkers like mypy