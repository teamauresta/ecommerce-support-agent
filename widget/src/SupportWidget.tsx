import React, { useState, useRef, useEffect, useCallback } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface SupportWidgetProps {
  storeId: string;
  apiUrl: string;
  position: 'bottom-right' | 'bottom-left';
}

export const SupportWidget: React.FC<SupportWidgetProps> = ({
  storeId,
  apiUrl,
  position,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when widget opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return;

    setError(null);
    setIsLoading(true);

    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');

    try {
      let response;
      
      if (!conversationId) {
        // Start new conversation
        response = await fetch(`${apiUrl}/api/v1/conversations`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            channel: 'widget',
            initial_message: content.trim(),
            context: {
              page_url: window.location.href,
            },
          }),
        });
      } else {
        // Continue conversation
        response = await fetch(`${apiUrl}/api/v1/conversations/${conversationId}/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: content.trim(),
          }),
        });
      }

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      const data = await response.json();
      
      // Save conversation ID
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }

      // Add assistant response
      const assistantMessage: Message = {
        id: data.message_id || `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response.content,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, assistantMessage]);

    } catch (err) {
      console.error('Error sending message:', err);
      setError('Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl, conversationId, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(inputValue);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputValue);
    }
  };

  const toggleWidget = () => {
    setIsOpen(!isOpen);
  };

  const positionStyles = position === 'bottom-right' 
    ? { right: '20px' } 
    : { left: '20px' };

  return (
    <>
      {/* Chat Button */}
      <button
        className="support-widget-button"
        style={positionStyles}
        onClick={toggleWidget}
        aria-label={isOpen ? 'Close support chat' : 'Open support chat'}
      >
        {isOpen ? (
          <CloseIcon />
        ) : (
          <ChatIcon />
        )}
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div className="support-widget-window" style={positionStyles}>
          {/* Header */}
          <div className="support-widget-header">
            <div className="support-widget-header-content">
              <div className="support-widget-avatar">🤖</div>
              <div>
                <div className="support-widget-title">Support</div>
                <div className="support-widget-subtitle">We typically reply instantly</div>
              </div>
            </div>
            <button 
              className="support-widget-close"
              onClick={toggleWidget}
              aria-label="Close chat"
            >
              <CloseIcon />
            </button>
          </div>

          {/* Messages */}
          <div className="support-widget-messages">
            {messages.length === 0 && (
              <div className="support-widget-welcome">
                <p>👋 Hi there! How can we help you today?</p>
                <div className="support-widget-quick-actions">
                  <button onClick={() => sendMessage("Where is my order?")}>
                    📦 Track my order
                  </button>
                  <button onClick={() => sendMessage("I want to return an item")}>
                    ↩️ Start a return
                  </button>
                  <button onClick={() => sendMessage("I need a refund")}>
                    💰 Request refund
                  </button>
                </div>
              </div>
            )}
            
            {messages.map((message) => (
              <div
                key={message.id}
                className={`support-widget-message support-widget-message-${message.role}`}
              >
                {message.role === 'assistant' && (
                  <div className="support-widget-message-avatar">🤖</div>
                )}
                <div className="support-widget-message-content">
                  {message.content}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="support-widget-message support-widget-message-assistant">
                <div className="support-widget-message-avatar">🤖</div>
                <div className="support-widget-typing">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}

            {error && (
              <div className="support-widget-error">
                {error}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form className="support-widget-input-form" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              type="text"
              className="support-widget-input"
              placeholder="Type your message..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              type="submit"
              className="support-widget-send"
              disabled={!inputValue.trim() || isLoading}
              aria-label="Send message"
            >
              <SendIcon />
            </button>
          </form>
        </div>
      )}
    </>
  );
};

// Icons
const ChatIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
);

const CloseIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

const SendIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);
