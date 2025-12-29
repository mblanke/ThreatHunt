/**
 * Analyst-assist agent chat panel component.
 * Provides context-aware guidance on artifact data and analysis.
 */

import React, { useState, useRef, useEffect } from "react";
import "./AgentPanel.css";
import {
  requestAgentAssistance,
  AssistResponse,
  AssistRequest,
} from "../utils/agentApi";

export interface AgentPanelProps {
  /** Name of the current dataset */
  dataset_name?: string;
  /** Type of artifact (e.g., FileList, ProcessList) */
  artifact_type?: string;
  /** Host name, IP, or identifier */
  host_identifier?: string;
  /** Summary of the uploaded data */
  data_summary?: string;
  /** Callback when user needs to execute analysis based on suggestions */
  onAnalysisAction?: (action: string) => void;
}

interface Message {
  role: "user" | "agent";
  content: string;
  response?: AssistResponse;
  timestamp: Date;
}

export const AgentPanel: React.FC<AgentPanelProps> = ({
  dataset_name,
  artifact_type,
  host_identifier,
  data_summary,
  onAnalysisAction,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      return;
    }

    // Add user message
    const userMessage: Message = {
      role: "user",
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setLoading(true);
    setError(null);

    try {
      // Build conversation history for context
      const conversation_history = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      // Request guidance from agent
      const response = await requestAgentAssistance({
        query: query,
        dataset_name,
        artifact_type,
        host_identifier,
        data_summary,
        conversation_history,
      });

      // Add agent response
      const agentMessage: Message = {
        role: "agent",
        content: response.guidance,
        response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, agentMessage]);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to get guidance";
      setError(errorMessage);

      // Add error message
      const errorMsg: Message = {
        role: "agent",
        content: `Error: ${errorMessage}. The agent service may be unavailable.`,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="agent-panel">
      <div className="agent-panel-header">
        <h3>Analyst Assist Agent</h3>
        <div className="agent-context">
          {host_identifier && (
            <span className="context-badge">Host: {host_identifier}</span>
          )}
          {artifact_type && (
            <span className="context-badge">Artifact: {artifact_type}</span>
          )}
          {dataset_name && (
            <span className="context-badge">Dataset: {dataset_name}</span>
          )}
        </div>
      </div>

      <div className="agent-messages">
        {messages.length === 0 ? (
          <div className="agent-welcome">
            <p className="welcome-title">Welcome to Analyst Assist</p>
            <p className="welcome-text">
              Ask questions about your artifact data. I can help you:
            </p>
            <ul>
              <li>Interpret and explain data patterns</li>
              <li>Suggest analytical pivots and filters</li>
              <li>Help form and test hypotheses</li>
              <li>Highlight anomalies and points of interest</li>
            </ul>
            <p className="welcome-note">
              💡 This agent provides guidance only. All analytical decisions
              remain with you.
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-header">
                <span className="message-role">
                  {msg.role === "user" ? "You" : "Agent"}
                </span>
                <span className="message-time">
                  {msg.timestamp.toLocaleTimeString()}
                </span>
              </div>

              <div className="message-content">{msg.content}</div>

              {msg.response && (
                <div className="message-details">
                  {msg.response.suggested_pivots.length > 0 && (
                    <div className="detail-section">
                      <h5>Suggested Pivots:</h5>
                      <ul>
                        {msg.response.suggested_pivots.map((pivot, i) => (
                          <li key={i}>
                            <button
                              className="pivot-button"
                              onClick={() =>
                                onAnalysisAction && onAnalysisAction(pivot)
                              }
                            >
                              {pivot}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {msg.response.suggested_filters.length > 0 && (
                    <div className="detail-section">
                      <h5>Suggested Filters:</h5>
                      <ul>
                        {msg.response.suggested_filters.map((filter, i) => (
                          <li key={i}>
                            <code>{filter}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {msg.response.caveats && (
                    <div className="detail-section caveats">
                      <h5>⚠️ Caveats:</h5>
                      <p>{msg.response.caveats}</p>
                    </div>
                  )}

                  {msg.response.confidence && (
                    <div className="detail-section">
                      <span className="confidence">
                        Confidence: {(msg.response.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {loading && (
          <div className="message agent loading">
            <div className="loading-indicator">
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}

        {error && (
          <div className="message agent error">
            <p className="error-text">⚠️ {error}</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="agent-input-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about your data, patterns, or next steps..."
          disabled={loading}
          className="agent-input"
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      <div className="agent-footer">
        <p className="footer-note">
          ℹ️ Agent provides guidance only. All decisions remain with the analyst.
        </p>
      </div>
    </div>
  );
};

export default AgentPanel;
