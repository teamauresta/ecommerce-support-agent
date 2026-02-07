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
              <div className="support-widget-avatar">
                <BotIcon />
              </div>
              <div>
                <div className="support-widget-title">Customer Support</div>
                <div className="support-widget-subtitle">Online • Ready to assist</div>
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
                <p>Welcome! How can we assist you today?</p>
                <div className="support-widget-quick-actions">
                  <button onClick={() => sendMessage("Track my order status")}>
                    <TrackIcon />
                    <span>Track order status</span>
                  </button>
                  <button onClick={() => sendMessage("I'd like to update my order details")}>
                    <EditIcon />
                    <span>Update order details</span>
                  </button>
                  <button onClick={() => sendMessage("I have a general question")}>
                    <HelpIcon />
                    <span>General inquiry</span>
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
                  <div className="support-widget-message-avatar">
                    <BotIcon />
                  </div>
                )}
                <div className="support-widget-message-content">
                  {message.content}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="support-widget-message support-widget-message-assistant">
                <div className="support-widget-message-avatar">
                  <BotIcon />
                </div>
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

// Premium SF Symbol-style Icons
const ChatIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
  </svg>
);

const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

const SendIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
    <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z"/>
  </svg>
);

const BotIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
    <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fontSize="18">💬</text>
  </svg>
);

const TrackIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
    <circle cx="12" cy="10" r="3"/>
  </svg>
);

const EditIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
  </svg>
);

const HelpIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
    <line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);
