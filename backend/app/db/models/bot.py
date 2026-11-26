"""
Bot Model

Represents chatbots created by organizations.
"""

from sqlalchemy import Column, String, Boolean, JSON, Text, Enum as SQLEnum, ForeignKey, ARRAY
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, SoftDeleteMixin
import uuid
import enum
import json


class BotStatus(str, enum.Enum):
    """Enumeration of bot statuses"""
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class Bot(Base, TimestampMixin, SoftDeleteMixin):
    """
    Bot model representing chatbots created by organizations.
    
    Each bot has its own knowledge base, settings, and widget configuration.
    """
    
    __tablename__ = "bots"
    
    # Primary Key
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique identifier for the bot"
    )
    
    # Foreign Keys
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the organization that owns this bot"
    )
    
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created this bot"
    )
    
    # Basic Information
    name = Column(
        String(255),
        nullable=False,
        comment="Bot name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Bot description"
    )
    
    avatar_url = Column(
        String(500),
        nullable=True,
        comment="URL to bot's avatar image"
    )
    
    # Status
    status = Column(
        SQLEnum(BotStatus),
        default=BotStatus.DRAFT,
        nullable=False,
        index=True,
        comment="Bot status (draft, active, inactive)"
    )
    
    # Bot Settings (JSON for flexibility)
    settings = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Bot behavior settings (tone, temperature, max_tokens, system_prompt, etc.)"
    )
    # Example structure:
    # {
    #     "tone": "professional",
    #     "temperature": 0.7,
    #     "max_tokens": 500,
    #     "model": "gpt-3.5-turbo",
    #     "system_prompt": "You are a helpful assistant...",
    #     "confidence_threshold": 0.7
    # }
    
    # Widget Settings (JSON for customization)
    widget_settings = Column(
        JSON,
        nullable=True,
        default=dict,
        comment="Widget appearance and behavior settings"
    )
    # Example structure:
    # {
    #     "colors": {
    #         "primary": "#007bff",
    #         "secondary": "#6c757d",
    #         "background": "#ffffff"
    #     },
    #     "position": "bottom-right",
    #     "welcome_message": "Hi! How can I help?",
    #     "suggested_questions": [...],
    #     "chat_icon": "default",
    #     "show_branding": true
    # }
    
    # API Key for widget authentication
    api_key = Column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
        comment="API key for widget authentication (plain text, will be hashed)"
    )
    
    api_key_hash = Column(
        String(255),
        nullable=True,
        comment="Hashed API key for secure storage"
    )
    
    # Allowed Domains (for widget security)
    allowed_domains = Column(
        ARRAY(String),
        nullable=True,
        default=list,
        comment="List of allowed domains for widget embedding"
    )
    
    # ========================================================================
    # RELATIONSHIPS
    # ========================================================================
    
    organization = relationship("Organization", back_populates="bots")
    creator = relationship("User", back_populates="created_bots", foreign_keys=[created_by])
    
    # Knowledge sources for this bot
    knowledge_sources = relationship(
        "KnowledgeSource",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    
    # Conversations for this bot
    conversations = relationship(
        "Conversation",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    
    # Chunks associated with this bot
    chunks = relationship(
        "Chunk",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    
    # Events for this bot
    events = relationship(
        "Event",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    
    # API keys for this bot
    api_keys = relationship(
        "ApiKey",
        back_populates="bot",
        cascade="all, delete-orphan"
    )
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"<Bot(id={self.id}, name={self.name}, status={self.status})>"
    
    def to_dict(self) -> dict:
        """Convert bot to dictionary"""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "name": self.name,
            "description": self.description,
            "avatar_url": self.avatar_url,
            "status": self.status.value,
            "settings": self.settings,
            "widget_settings": self.widget_settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def get_widget_script(self) -> str:
        """Generate embeddable widget script"""
        # Get widget settings with defaults
        settings = self.widget_settings or {}
        colors = settings.get("colors", {
            "primary": "#007bff",
            "secondary": "#6c757d",
            "background": "#ffffff",
            "text": "#212529"
        })
        position = settings.get("position", "bottom-right")
        welcome_message = settings.get("welcome_message", "Hi! How can I help you today?")
        suggested_questions = settings.get("suggested_questions", [])
        chat_icon = settings.get("chat_icon", "default")
        show_branding = settings.get("show_branding", True)
        height = settings.get("height", "500px")
        width = settings.get("width", "350px")
        auto_open = settings.get("auto_open", False)
        z_index = settings.get("z_index", 10000)
        
        # Generate position CSS
        position_css = ""
        if position == "bottom-right":
            position_css = "right: 20px; bottom: 20px;"
        elif position == "bottom-left":
            position_css = "left: 20px; bottom: 20px;"
        elif position == "top-right":
            position_css = "right: 20px; top: 20px;"
        elif position == "top-left":
            position_css = "left: 20px; top: 20px;"
        
        # Generate chat icon based on type
        chat_icon_svg = ""
        if chat_icon == "message":
            chat_icon_svg = """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
            """
        elif chat_icon == "chat":
            chat_icon_svg = """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M12 1C5.92 1 1 5.02 1 10c0 2.68 1.42 5.1 3.65 6.71V22l6.26-3.48c.35.05.71.08 1.09.08 6.08 0 11-4.02 11-9S18.08 1 12 1z"/>
            </svg>
            """
        elif chat_icon == "help":
            chat_icon_svg = """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/>
            </svg>
            """
        else:  # default
            chat_icon_svg = """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
            """
        
        # Generate suggested questions HTML
        suggested_questions_html = ""
        if suggested_questions:
            questions_items = ""
            for question in suggested_questions:
                if isinstance(question, dict) and "text" in question:
                    questions_items += f"""
                    <div class="rag-suggested-question" onclick="ragChatbot.sendMessage('{question['text']}')">
                        {question['text']}
                    </div>
                    """
                else:
                    questions_items += f"""
                    <div class="rag-suggested-question" onclick="ragChatbot.sendMessage('{question}')">
                        {question}
                    </div>
                    """
            
            suggested_questions_html = f"""
            <div class="rag-suggested-questions">
                {questions_items}
            </div>
            """
        
        # Generate branding HTML
        branding_html = ""
        if show_branding:
            branding_html = """
            <div class="rag-branding">
                Powered by <a href="https://example.com" target="_blank">RAG Chatbot</a>
            </div>
            """
        
        # Generate the widget script using regular string (NOT f-string)
        # Use .format() to inject Python variables
        script = """
    (function() {{
        // Configuration
        const botConfig = {{
            botId: '{bot_id}',
            apiKey: '{api_key}',
            apiEndpoint: '/api/v1/widget',
            name: '{name}',
            description: '{description}',
            avatarUrl: '{avatar_url}',
            colors: {colors_json},
            position: '{position}',
            welcomeMessage: '{welcome_message}',
            suggestedQuestions: {suggested_questions_json},
            height: '{height}',
            width: '{width}',
            autoOpen: {auto_open_js},
            zIndex: {z_index},
            showBranding: {show_branding_js}
        }};

        // Create global chatbot object
        window.ragChatbot = {{}};
        
        // Create widget container
        const widgetContainer = document.createElement('div');
        widgetContainer.id = 'rag-chatbot-widget';
        widgetContainer.style.cssText = `
            position: fixed;
            {position_css}
            width: ${{botConfig.width}};
            height: ${{botConfig.height}};
            background: ${{botConfig.colors.background}};
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: ${{botConfig.zIndex}};
            display: none;
            flex-direction: column;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            overflow: hidden;
        `;
        
        // Create chat button
        const chatButton = document.createElement('div');
        chatButton.id = 'rag-chatbot-button';
        chatButton.style.cssText = `
            position: fixed;
            {position_css}
            width: 60px;
            height: 60px;
            background: ${{botConfig.colors.primary}};
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: ${{botConfig.zIndex + 1}};
            transition: transform 0.2s ease;
        `;
        
        // Add chat icon
        chatButton.innerHTML = `{chat_icon_svg}`;
        
        // Create widget header
        const widgetHeader = document.createElement('div');
        widgetHeader.style.cssText = `
            background: ${{botConfig.colors.primary}};
            color: white;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        `;
        
        // Add bot info to header
        widgetHeader.innerHTML = `
            <div style="display: flex; align-items: center;">
                ${{botConfig.avatarUrl ? `<img src="${{botConfig.avatarUrl}}" alt="Bot Avatar" style="width: 30px; height: 30px; border-radius: 50%; margin-right: 10px;">` : ''}}
                <div>
                    <div style="font-weight: bold;">${{botConfig.name}}</div>
                    ${{botConfig.description ? `<div style="font-size: 12px; opacity: 0.8;">${{botConfig.description}}</div>` : ''}}
                </div>
            </div>
            <div id="rag-chatbot-close" style="cursor: pointer;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
            </div>
        `;
        
        // Create chat messages container
        const messagesContainer = document.createElement('div');
        messagesContainer.id = 'rag-chatbot-messages';
        messagesContainer.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        
        // Add welcome message
        messagesContainer.innerHTML = `
            <div class="rag-message rag-bot-message" style="
                background: ${{botConfig.colors.secondary}}15;
                padding: 10px 15px;
                border-radius: 18px;
                border-top-left-radius: 5px;
                max-width: 80%;
                align-self: flex-start;
            ">
                ${{botConfig.welcomeMessage}}
            </div>
            
            {suggested_questions_html}
        `;
        
        // Create input area
        const inputArea = document.createElement('div');
        inputArea.style.cssText = `
            padding: 15px;
            border-top: 1px solid #eee;
            display: flex;
            gap: 10px;
        `;
        
        // Add input and send button
        inputArea.innerHTML = `
            <input id="rag-chatbot-input" type="text" placeholder="Type your message..." style="
                flex: 1;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 20px;
                outline: none;
            ">
            <button id="rag-chatbot-send" style="
                background: ${{botConfig.colors.primary}};
                color: white;
                border: none;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
            ">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
            </button>
        `;
        
        // Add branding if enabled
        if (botConfig.showBranding) {{
            const branding = document.createElement('div');
            branding.style.cssText = `
                padding: 5px 15px;
                text-align: center;
                font-size: 12px;
                color: #999;
                border-top: 1px solid #eee;
            `;
            branding.innerHTML = `
                Powered by <a href="https://example.com" target="_blank" style="color: ${{botConfig.colors.primary}};">RAG Chatbot</a>
            `;
            widgetContainer.appendChild(branding);
        }}
        
        // Add components to widget container
        widgetContainer.appendChild(widgetHeader);
        widgetContainer.appendChild(messagesContainer);
        widgetContainer.appendChild(inputArea);
        
        // Add styles
        const styles = document.createElement('style');
        styles.textContent = `
            .rag-message {{
                word-break: break-word;
                line-height: 1.5;
            }}
            
            .rag-bot-message {{
                background: ${{botConfig.colors.secondary}}15;
                padding: 10px 15px;
                border-radius: 18px;
                border-top-left-radius: 5px;
                max-width: 80%;
                align-self: flex-start;
            }}
            
            .rag-user-message {{
                background: ${{botConfig.colors.primary}};
                color: white;
                padding: 10px 15px;
                border-radius: 18px;
                border-top-right-radius: 5px;
                max-width: 80%;
                align-self: flex-end;
            }}
            
            .rag-suggested-questions {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                margin-top: 15px;
            }}
            
            .rag-suggested-question {{
                background: ${{botConfig.colors.secondary}}10;
                padding: 8px 15px;
                border-radius: 18px;
                cursor: pointer;
                font-size: 14px;
                border: 1px solid ${{botConfig.colors.secondary}}20;
                transition: background 0.2s;
            }}
            
            .rag-suggested-question:hover {{
                background: ${{botConfig.colors.secondary}}20;
            }}
            
            .rag-source {{
                font-size: 12px;
                color: #666;
                margin-top: 5px;
            }}
            
            .rag-typing {{
                display: flex;
                align-items: center;
                gap: 5px;
                padding: 10px 15px;
                background: ${{botConfig.colors.secondary}}15;
                border-radius: 18px;
                border-top-left-radius: 5px;
                max-width: 80%;
                align-self: flex-start;
            }}
            
            .rag-typing-dot {{
                width: 8px;
                height: 8px;
                background: ${{botConfig.colors.secondary}};
                border-radius: 50%;
                animation: rag-typing 1s infinite ease-in-out;
            }}
            
            .rag-typing-dot:nth-child(1) {{ animation-delay: 0s; }}
            .rag-typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
            .rag-typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}
            
            @keyframes rag-typing {{
                0%, 100% {{ transform: translateY(0); }}
                50% {{ transform: translateY(-5px); }}
            }}
        `;
        
        // Add to page
        document.head.appendChild(styles);
        document.body.appendChild(chatButton);
        document.body.appendChild(widgetContainer);
        
        // Event handlers
        chatButton.addEventListener('click', function() {{
            widgetContainer.style.display = 'flex';
            chatButton.style.display = 'none';
            document.getElementById('rag-chatbot-input').focus();
        }});
        
        document.getElementById('rag-chatbot-close').addEventListener('click', function() {{
            widgetContainer.style.display = 'none';
            chatButton.style.display = 'flex';
        }});
        
        // Hover effects
        chatButton.addEventListener('mouseenter', function() {{
            this.style.transform = 'scale(1.1)';
        }});
        
        chatButton.addEventListener('mouseleave', function() {{
            this.style.transform = 'scale(1)';
        }});
        
        // Send message function
        function sendMessage(message) {{
            if (!message.trim()) return;
            
            // Add user message to chat
            const messagesContainer = document.getElementById('rag-chatbot-messages');
            messagesContainer.innerHTML += `
                <div class="rag-user-message">
                    ${{message}}
                </div>
            `;
            
            // Add typing indicator
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'rag-typing';
            typingIndicator.innerHTML = `
                <div class="rag-typing-dot"></div>
                <div class="rag-typing-dot"></div>
                <div class="rag-typing-dot"></div>
            `;
            messagesContainer.appendChild(typingIndicator);
            
            // Scroll to bottom
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            
            // Clear input
            document.getElementById('rag-chatbot-input').value = '';
            
            // Send message to API (mock for now)
            setTimeout(() => {{
                // Remove typing indicator
                messagesContainer.removeChild(typingIndicator);
                
                // Add bot response
                messagesContainer.innerHTML += `
                    <div class="rag-bot-message">
                        This is a sample response. In a real implementation, this would call the widget API endpoint.
                        <div class="rag-source">Source: Sample Data</div>
                    </div>
                `;
                
                // Scroll to bottom
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }}, 1500);
        }}
        
        // Handle send button click
        document.getElementById('rag-chatbot-send').addEventListener('click', function() {{
            const input = document.getElementById('rag-chatbot-input');
            sendMessage(input.value);
        }});
        
        // Handle enter key
        document.getElementById('rag-chatbot-input').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                sendMessage(this.value);
            }}
        }});
        
        // Expose sendMessage function
        window.ragChatbot.sendMessage = sendMessage;
        
        // Auto-open if configured
        if (botConfig.autoOpen) {{
            setTimeout(() => {{
                widgetContainer.style.display = 'flex';
                chatButton.style.display = 'none';
            }}, 1000);
        }}
        
        console.log('RAG Chatbot Widget loaded for bot:', botConfig.botId);
    }})();
        """.format(
            bot_id=self.id,
            api_key=self.api_key or "",
            name=self.name,
            description=self.description or "",
            avatar_url=self.avatar_url or "",
            colors_json=json.dumps(colors),
            position=position,
            welcome_message=welcome_message,
            suggested_questions_json=json.dumps(suggested_questions),
            height=height,
            width=width,
            auto_open_js=str(auto_open).lower(),
            z_index=z_index,
            show_branding_js=str(show_branding).lower(),
            position_css=position_css,
            chat_icon_svg=chat_icon_svg,
            suggested_questions_html=suggested_questions_html
        )
        
        return script



#     def get_widget_script(self) -> str:
#         """Generate embeddable widget script"""
#         # Get widget settings with defaults
#         settings = self.widget_settings or {}
#         colors = settings.get("colors", {
#             "primary": "#007bff",
#             "secondary": "#6c757d",
#             "background": "#ffffff",
#             "text": "#212529"
#         })
#         position = settings.get("position", "bottom-right")
#         welcome_message = settings.get("welcome_message", "Hi! How can I help you today?")
#         suggested_questions = settings.get("suggested_questions", [])
#         chat_icon = settings.get("chat_icon", "default")
#         show_branding = settings.get("show_branding", True)
#         height = settings.get("height", "500px")
#         width = settings.get("width", "350px")
#         auto_open = settings.get("auto_open", False)
#         z_index = settings.get("z_index", 10000)
        
#         # Generate position CSS
#         position_css = ""
#         if position == "bottom-right":
#             position_css = "right: 20px; bottom: 20px;"
#         elif position == "bottom-left":
#             position_css = "left: 20px; bottom: 20px;"
#         elif position == "top-right":
#             position_css = "right: 20px; top: 20px;"
#         elif position == "top-left":
#             position_css = "left: 20px; top: 20px;"
        
#         # Generate chat icon based on type
#         chat_icon_svg = ""
#         if chat_icon == "message":
#             chat_icon_svg = """
#             <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
#                 <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
#             </svg>
#             """
#         elif chat_icon == "chat":
#             chat_icon_svg = """
#             <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
#                 <path d="M12 1C5.92 1 1 5.02 1 10c0 2.68 1.42 5.1 3.65 6.71V22l6.26-3.48c.35.05.71.08 1.09.08 6.08 0 11-4.02 11-9S18.08 1 12 1z"/>
#             </svg>
#             """
#         elif chat_icon == "help":
#             chat_icon_svg = """
#             <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
#                 <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/>
#             </svg>
#             """
#         else:  # default
#             chat_icon_svg = """
#             <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
#                 <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l4 4 4-4h4c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
#             </svg>
#             """
        
#         # Generate suggested questions HTML
#         suggested_questions_html = ""
#         if suggested_questions:
#             questions_items = ""
#             for question in suggested_questions:
#                 if isinstance(question, dict) and "text" in question:
#                     questions_items += f"""
#                     <div class="rag-suggested-question" onclick="ragChatbot.sendMessage('{question['text']}')">
#                         {question['text']}
#                     </div>
#                     """
#                 else:
#                     questions_items += f"""
#                     <div class="rag-suggested-question" onclick="ragChatbot.sendMessage('{question}')">
#                         {question}
#                     </div>
#                     """
            
#             suggested_questions_html = f"""
#             <div class="rag-suggested-questions">
#                 {questions_items}
#             </div>
#             """
        
#         # Generate branding HTML
#         branding_html = ""
#         if show_branding:
#             branding_html = """
#             <div class="rag-branding">
#                 Powered by <a href="https://example.com" target="_blank">RAG Chatbot</a>
#             </div>
#             """
        
#         # Generate the widget script
#         return f"""
# (function() {{
#     // Configuration
#     const botConfig = {{
#         botId: '{self.id}',
#         apiKey: '{self.api_key or ""}',
#         apiEndpoint: '/api/v1/widget',
#         name: '{self.name}',
#         description: '{self.description or ""}',
#         avatarUrl: '{self.avatar_url or ""}',
#         colors: {json.dumps(colors)},
#         position: '{position}',
#         welcomeMessage: '{welcome_message}',
#         suggestedQuestions: {json.dumps(suggested_questions)},
#         height: '{height}',
#         width: '{width}',
#         autoOpen: {str(auto_open).lower()},
#         zIndex: {z_index},
#         showBranding: {str(show_branding).lower()}
#     }};

#     // Create global chatbot object
#     window.ragChatbot = {{}};
    
#     // Create widget container
#     const widgetContainer = document.createElement('div');
#     widgetContainer.id = 'rag-chatbot-widget';
#     widgetContainer.style.cssText = `
#         position: fixed;
#         {position_css}
#         width: ${{botConfig.width}};
#         height: ${{botConfig.height}};
#         background: ${{botConfig.colors.background}};
#         border-radius: 10px;
#         box-shadow: 0 4px 20px rgba(0,0,0,0.15);
#         z-index: ${{botConfig.zIndex}};
#         display: none;
#         flex-direction: column;
#         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
#         overflow: hidden;
#     `;
    
#     // Create chat button
#     const chatButton = document.createElement('div');
#     chatButton.id = 'rag-chatbot-button';
#     chatButton.style.cssText = `
#         position: fixed;
#         {position_css}
#         width: 60px;
#         height: 60px;
#         background: ${{botConfig.colors.primary}};
#         border-radius: 50%;
#         cursor: pointer;
#         display: flex;
#         align-items: center;
#         justify-content: center;
#         box-shadow: 0 4px 20px rgba(0,0,0,0.15);
#         z-index: ${{botConfig.zIndex + 1}};
#         transition: transform 0.2s ease;
#     `;
    
#     // Add chat icon
#     chatButton.innerHTML = `{chat_icon_svg}`;
    
#     // Create widget header
#     const widgetHeader = document.createElement('div');
#     widgetHeader.style.cssText = `
#         background: ${{botConfig.colors.primary}};
#         color: white;
#         padding: 15px;
#         display: flex;
#         justify-content: space-between;
#         align-items: center;
#         border-top-left-radius: 10px;
#         border-top-right-radius: 10px;
#     `;
    
#     // Add bot info to header
#     widgetHeader.innerHTML = `
#         <div style="display: flex; align-items: center;">
#             ${{botConfig.avatarUrl ? `<img src="${{botConfig.avatarUrl}}" alt="Bot Avatar" style="width: 30px; height: 30px; border-radius: 50%; margin-right: 10px;">` : ''}}
#             <div>
#                 <div style="font-weight: bold;">${{botConfig.name}}</div>
#                 ${{botConfig.description ? `<div style="font-size: 12px; opacity: 0.8;">${{botConfig.description}}</div>` : ''}}
#             </div>
#         </div>
#         <div id="rag-chatbot-close" style="cursor: pointer;">
#             <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
#                 <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
#             </svg>
#         </div>
#     `;
    
#     // Create chat messages container
#     const messagesContainer = document.createElement('div');
#     messagesContainer.id = 'rag-chatbot-messages';
#     messagesContainer.style.cssText = `
#         flex: 1;
#         overflow-y: auto;
#         padding: 15px;
#         display: flex;
#         flex-direction: column;
#         gap: 10px;
#     `;
    
#     // Add welcome message
#     messagesContainer.innerHTML = `
#         <div class="rag-message rag-bot-message" style="
#             background: ${{botConfig.colors.secondary}}15;
#             padding: 10px 15px;
#             border-radius: 18px;
#             border-top-left-radius: 5px;
#             max-width: 80%;
#             align-self: flex-start;
#         ">
#             ${{botConfig.welcomeMessage}}
#         </div>
        
#         {suggested_questions_html}
#     `;
    
#     // Create input area
#     const inputArea = document.createElement('div');
#     inputArea.style.cssText = `
#         padding: 15px;
#         border-top: 1px solid #eee;
#         display: flex;
#         gap: 10px;
#     `;
    
#     // Add input and send button
#     inputArea.innerHTML = `
#         <input id="rag-chatbot-input" type="text" placeholder="Type your message..." style="
#             flex: 1;
#             padding: 10px;
#             border: 1px solid #ddd;
#             border-radius: 20px;
#             outline: none;
#         ">
#         <button id="rag-chatbot-send" style="
#             background: ${{botConfig.colors.primary}};
#             color: white;
#             border: none;
#             border-radius: 50%;
#             width: 40px;
#             height: 40px;
#             display: flex;
#             align-items: center;
#             justify-content: center;
#             cursor: pointer;
#         ">
#             <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
#                 <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
#             </svg>
#         </button>
#     `;
    
#     // Add branding if enabled
#     if (botConfig.showBranding) {
#         const branding = document.createElement('div');
#         branding.style.cssText = `
#             padding: 5px 15px;
#             text-align: center;
#             font-size: 12px;
#             color: #999;
#             border-top: 1px solid #eee;
#         `;
#         branding.innerHTML = `
#             Powered by <a href="https://example.com" target="_blank" style="color: ${{botConfig.colors.primary}};">RAG Chatbot</a>
#         `;
#         widgetContainer.appendChild(branding);
#     }
    
#     // Add components to widget container
#     widgetContainer.appendChild(widgetHeader);
#     widgetContainer.appendChild(messagesContainer);
#     widgetContainer.appendChild(inputArea);
    
#     // Add styles
#     const styles = document.createElement('style');
#     styles.textContent = `
#         .rag-message {
#             word-break: break-word;
#             line-height: 1.5;
#         }
        
#         .rag-bot-message {
#             background: ${{botConfig.colors.secondary}}15;
#             padding: 10px 15px;
#             border-radius: 18px;
#             border-top-left-radius: 5px;
#             max-width: 80%;
#             align-self: flex-start;
#         }
        
#         .rag-user-message {
#             background: ${{botConfig.colors.primary}};
#             color: white;
#             padding: 10px 15px;
#             border-radius: 18px;
#             border-top-right-radius: 5px;
#             max-width: 80%;
#             align-self: flex-end;
#         }
        
#         .rag-suggested-questions {
#             display: flex;
#             flex-direction: column;
#             gap: 8px;
#             margin-top: 15px;
#         }
        
#         .rag-suggested-question {
#             background: ${{botConfig.colors.secondary}}10;
#             padding: 8px 15px;
#             border-radius: 18px;
#             cursor: pointer;
#             font-size: 14px;
#             border: 1px solid ${{botConfig.colors.secondary}}20;
#             transition: background 0.2s;
#         }
        
#         .rag-suggested-question:hover {
#             background: ${{botConfig.colors.secondary}}20;
#         }
        
#         .rag-source {
#             font-size: 12px;
#             color: #666;
#             margin-top: 5px;
#         }
        
#         .rag-typing {
#             display: flex;
#             align-items: center;
#             gap: 5px;
#             padding: 10px 15px;
#             background: ${{botConfig.colors.secondary}}15;
#             border-radius: 18px;
#             border-top-left-radius: 5px;
#             max-width: 80%;
#             align-self: flex-start;
#         }
        
#         .rag-typing-dot {
#             width: 8px;
#             height: 8px;
#             background: ${{botConfig.colors.secondary}};
#             border-radius: 50%;
#             animation: rag-typing 1s infinite ease-in-out;
#         }
        
#         .rag-typing-dot:nth-child(1) {{ animation-delay: 0s; }}
#         .rag-typing-dot:nth-child(2) {{ animation-delay: 0.2s; }}
#         .rag-typing-dot:nth-child(3) {{ animation-delay: 0.4s; }}
        
#         @keyframes rag-typing {{
#             0%, 100% {{ transform: translateY(0); }}
#             50% {{ transform: translateY(-5px); }}
#         }}
#     `;
    
#     // Add to page
#     document.head.appendChild(styles);
#     document.body.appendChild(chatButton);
#     document.body.appendChild(widgetContainer);
    
#     // Event handlers
#     chatButton.addEventListener('click', function() {{
#         widgetContainer.style.display = 'flex';
#         chatButton.style.display = 'none';
#         document.getElementById('rag-chatbot-input').focus();
#     }});
    
#     document.getElementById('rag-chatbot-close').addEventListener('click', function() {{
#         widgetContainer.style.display = 'none';
#         chatButton.style.display = 'flex';
#     }});
    
#     // Hover effects
#     chatButton.addEventListener('mouseenter', function() {{
#         this.style.transform = 'scale(1.1)';
#     }});
    
#     chatButton.addEventListener('mouseleave', function() {{
#         this.style.transform = 'scale(1)';
#     }});
    
#     // Send message function
#     function sendMessage(message) {{
#         if (!message.trim()) return;
        
#         // Add user message to chat
#         const messagesContainer = document.getElementById('rag-chatbot-messages');
#         messagesContainer.innerHTML += `
#             <div class="rag-user-message">
#                 ${{message}}
#             </div>
#         `;
        
#         // Add typing indicator
#         const typingIndicator = document.createElement('div');
#         typingIndicator.className = 'rag-typing';
#         typingIndicator.innerHTML = `
#             <div class="rag-typing-dot"></div>
#             <div class="rag-typing-dot"></div>
#             <div class="rag-typing-dot"></div>
#         `;
#         messagesContainer.appendChild(typingIndicator);
        
#         // Scroll to bottom
#         messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
#         // Clear input
#         document.getElementById('rag-chatbot-input').value = '';
        
#         // Send message to API (mock for now)
#         setTimeout(() => {{
#             // Remove typing indicator
#             messagesContainer.removeChild(typingIndicator);
            
#             // Add bot response
#             messagesContainer.innerHTML += `
#                 <div class="rag-bot-message">
#                     This is a sample response. In a real implementation, this would call the widget API endpoint.
#                     <div class="rag-source">Source: Sample Data</div>
#                 </div>
#             `;
            
#             // Scroll to bottom
#             messagesContainer.scrollTop = messagesContainer.scrollHeight;
#         }}, 1500);
#     }}
    
#     // Handle send button click
#     document.getElementById('rag-chatbot-send').addEventListener('click', function() {{
#         const input = document.getElementById('rag-chatbot-input');
#         sendMessage(input.value);
#     }});
    
#     // Handle enter key
#     document.getElementById('rag-chatbot-input').addEventListener('keypress', function(e) {{
#         if (e.key === 'Enter') {{
#             sendMessage(this.value);
#         }}
#     }});
    
#     // Expose sendMessage function
#     window.ragChatbot.sendMessage = sendMessage;
    
#     // Auto-open if configured
#     if (botConfig.autoOpen) {{
#         setTimeout(() => {{
#             widgetContainer.style.display = 'flex';
#             chatButton.style.display = 'none';
#         }}, 1000);
#     }}
    
#     console.log('RAG Chatbot Widget loaded for bot:', botConfig.botId);
# }})();
#         """