"""
LLM Service

Handles integration with OpenAI API for generating responses:
- OpenAI API integration
- Prompt engineering
- Response streaming (SSE)
- Error handling
- Token counting
"""

import logging
import openai
from typing import List, Dict, Any, Optional, AsyncGenerator
import json
import time

from app.config import settings
from app.core.exceptions import LLMException
from app.services.cache_service import get_response_cache

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with OpenAI API for generating responses.
    """
    
    def __init__(self):
        """Initialize LLM service."""
        # Initialize OpenAI client with environment variables
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            organization=settings.OPENAI_ORGANIZATION,
            timeout=settings.LLM_TIMEOUT_SECONDS
        )
        
        # Default model settings
        self.default_model = settings.DEFAULT_LLM_MODEL
        self.default_temperature = settings.DEFAULT_LLM_TEMPERATURE
        self.default_max_tokens = settings.DEFAULT_MAX_TOKENS
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.available_models = settings.AVAILABLE_MODELS
        
        # Response cache
        self.response_cache = get_response_cache()
        
        # System prompt templates
        self.system_prompts = {
            "default": """You are a helpful AI assistant that answers questions based on the provided knowledge base. 

Guidelines:
- Use the provided context to answer questions accurately
- If the context doesn't contain enough information, say so clearly
- Cite sources when referencing specific information
- Be concise but comprehensive
- Maintain a professional and helpful tone
- If asked about something not in the knowledge base, politely explain that you don't have that information

Context from knowledge base:
{knowledge_context}

Previous conversation:
{conversation_context}""",
            
            "support": """You are a customer support AI assistant. Your role is to help customers with their questions and issues.

Guidelines:
- Be empathetic and understanding
- Provide clear, step-by-step solutions when possible
- Escalate complex issues that require human intervention
- Use the knowledge base to provide accurate information
- Maintain a professional but friendly tone
- If you cannot resolve an issue, offer to connect them with a human agent

Context from knowledge base:
{knowledge_context}

Previous conversation:
{conversation_context}""",
            
            "technical": """You are a technical AI assistant specializing in technical documentation and support.

Guidelines:
- Provide detailed technical explanations
- Include code examples when relevant
- Reference specific documentation sections
- Be precise with technical terminology
- Offer troubleshooting steps for technical issues
- If the question is beyond the scope of the knowledge base, suggest where to find more information

Context from knowledge base:
{knowledge_context}

Previous conversation:
{conversation_context}"""
        }
    
    def generate_response(
        self,
        user_message: str,
        context_messages: List[Dict[str, Any]] = None,
        knowledge_context: str = "",
        bot_settings: Dict[str, Any] = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        Generate a response using OpenAI API.
        
        Args:
            user_message: Current user message
            context_messages: Previous conversation context
            knowledge_context: Retrieved knowledge context
            bot_settings: Bot-specific settings
            system_prompt: Custom system prompt
            
        Returns:
            Response with content and metadata
        """
        try:
            start_time = time.time()
            
            # Prepare bot settings
            bot_settings = bot_settings or {}
            model = bot_settings.get("model", self.default_model)
            temperature = bot_settings.get("temperature", self.default_temperature)
            max_tokens = bot_settings.get("max_tokens", self.default_max_tokens)
            tone = bot_settings.get("tone", "default")
            bot_id = bot_settings.get("bot_id", "default")
            
            # Generate context hash for caching
            context_hash = self.response_cache.generate_context_hash(
                context_messages or [],
                knowledge_context
            )
            
            # Check cache first (only for low temperature responses)
            if temperature <= 0.1:  # Only cache deterministic responses
                cached_response = self.response_cache.get_response(
                    user_message=user_message,
                    context_hash=context_hash,
                    bot_id=bot_id
                )
                
                if cached_response is not None:
                    logger.debug(f"Cache hit for LLM response: {user_message[:50]}...")
                    return {
                        "content": cached_response,
                        "model_used": model,
                        "token_count": 0,  # Cached response
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "latency_ms": (time.time() - start_time) * 1000,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "cached": True
                    }
            
            # Build system prompt
            if system_prompt:
                final_system_prompt = system_prompt
            else:
                prompt_template = self.system_prompts.get(tone, self.system_prompts["default"])
                final_system_prompt = prompt_template.format(
                    knowledge_context=knowledge_context,
                    conversation_context=self._format_conversation_context(context_messages or [])
                )
            
            # Build messages for OpenAI
            messages = [{"role": "system", "content": final_system_prompt}]
            
            # Add conversation context (last few messages)
            if context_messages:
                for msg in context_messages[-6:]:  # Limit to last 6 messages
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Make API call
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response
            ai_response = response.choices[0].message.content
            usage = response.usage
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Cache the response (only for low temperature)
            if temperature <= 0.1:
                self.response_cache.set_response(
                    user_message=user_message,
                    context_hash=context_hash,
                    bot_id=bot_id,
                    response=ai_response
                )
            
            logger.info(
                f"LLM response generated: model={model}, "
                f"tokens={usage.total_tokens}, latency={latency_ms:.2f}ms"
            )
            
            return {
                "content": ai_response,
                "model_used": model,
                "token_count": usage.total_tokens,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "latency_ms": latency_ms,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "cached": False
            }
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {str(e)}")
            raise LLMException("Rate limit exceeded. Please try again later.")
        
        except openai.BadRequestError as e:
            logger.error(f"Invalid OpenAI request: {str(e)}")
            raise LLMException("Invalid request. Please check your input.")
        
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {str(e)}")
            raise LLMException("Authentication error. Please check API configuration.")
        
        except openai.APITimeoutError as e:
            logger.error(f"OpenAI timeout: {str(e)}")
            raise LLMException("Request timeout. Please try again.")
        
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise LLMException(f"Failed to generate response: {str(e)}")
    
    def generate_response_stream(
        self,
        user_message: str,
        context_messages: List[Dict[str, Any]] = None,
        knowledge_context: str = "",
        bot_settings: Dict[str, Any] = None,
        system_prompt: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response using OpenAI API.
        
        Args:
            user_message: Current user message
            context_messages: Previous conversation context
            knowledge_context: Retrieved knowledge context
            bot_settings: Bot-specific settings
            system_prompt: Custom system prompt
            
        Yields:
            Streaming response chunks
        """
        try:
            # Prepare bot settings
            bot_settings = bot_settings or {}
            model = bot_settings.get("model", self.default_model)
            temperature = bot_settings.get("temperature", self.default_temperature)
            max_tokens = bot_settings.get("max_tokens", self.default_max_tokens)
            tone = bot_settings.get("tone", "default")
            
            # Build system prompt
            if system_prompt:
                final_system_prompt = system_prompt
            else:
                prompt_template = self.system_prompts.get(tone, self.system_prompts["default"])
                final_system_prompt = prompt_template.format(
                    knowledge_context=knowledge_context,
                    conversation_context=self._format_conversation_context(context_messages or [])
                )
            
            # Build messages for OpenAI
            messages = [{"role": "system", "content": final_system_prompt}]
            
            # Add conversation context
            if context_messages:
                for msg in context_messages[-6:]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Make streaming API call
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            # Stream response chunks
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
        except Exception as e:
            logger.error(f"Streaming response error: {str(e)}")
            yield f"Error: {str(e)}"
    
    def _format_conversation_context(
        self,
        context_messages: List[Dict[str, Any]]
    ) -> str:
        """
        Format conversation context for system prompt.
        
        Args:
            context_messages: List of conversation messages
            
        Returns:
            Formatted conversation context
        """
        if not context_messages:
            return "No previous conversation."
        
        formatted_messages = []
        for msg in context_messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted_messages.append(f"{role}: {msg['content']}")
        
        return "\n".join(formatted_messages)
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        # Rough estimation: 1 token ≈ 4 characters for English
        return len(text) // 4
    
    def validate_model(self, model: str) -> bool:
        """
        Validate if model is supported.
        
        Args:
            model: Model name to validate
            
        Returns:
            True if model is supported
        """
        return model in self.available_models
    
    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get information about a model.
        
        Args:
            model: Model name
            
        Returns:
            Model information
        """
        model_info = {
            "gpt-3.5-turbo": {
                "name": "GPT-3.5 Turbo",
                "max_tokens": 4096,
                "cost_per_1k_tokens": 0.002,
                "description": "Fast and efficient for most tasks"
            },
            "gpt-3.5-turbo-16k": {
                "name": "GPT-3.5 Turbo 16K",
                "max_tokens": 16384,
                "cost_per_1k_tokens": 0.004,
                "description": "Extended context for longer conversations"
            },
            "gpt-4": {
                "name": "GPT-4",
                "max_tokens": 8192,
                "cost_per_1k_tokens": 0.03,
                "description": "Most capable model for complex tasks"
            },
            "gpt-4-32k": {
                "name": "GPT-4 32K",
                "max_tokens": 32768,
                "cost_per_1k_tokens": 0.06,
                "description": "Extended context GPT-4"
            },
            "gpt-4-turbo": {
                "name": "GPT-4 Turbo",
                "max_tokens": 128000,
                "cost_per_1k_tokens": 0.01,
                "description": "Latest GPT-4 with extended context"
            }
        }
        
        return model_info.get(model, {
            "name": model,
            "max_tokens": 4096,
            "cost_per_1k_tokens": 0.002,
            "description": "Unknown model"
        })
    
    def get_available_models(self) -> List[str]:
        """
        Get list of available models from settings.
        
        Returns:
            List of available model names
        """
        return self.available_models.copy()
    
    def get_client_config(self) -> Dict[str, Any]:
        """
        Get current OpenAI client configuration.
        
        Returns:
            Client configuration information
        """
        return {
            "base_url": settings.OPENAI_BASE_URL,
            "organization": settings.OPENAI_ORGANIZATION,
            "timeout": settings.LLM_TIMEOUT_SECONDS,
            "default_model": self.default_model,
            "available_models": self.available_models
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create a singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get the global LLM service instance.
    
    Returns:
        LLMService: Global instance
    """
    global _llm_service
    
    if _llm_service is None:
        _llm_service = LLMService()
    
    return _llm_service
