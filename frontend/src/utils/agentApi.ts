/**
 * API utility functions for agent communication.
 */

export interface AssistRequest {
  query: string;
  dataset_name?: string;
  artifact_type?: string;
  host_identifier?: string;
  data_summary?: string;
  conversation_history?: Array<{ role: string; content: string }>;
}

export interface AssistResponse {
  guidance: string;
  confidence: number;
  suggested_pivots: string[];
  suggested_filters: string[];
  caveats?: string;
  reasoning?: string;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

/**
 * Request guidance from the analyst-assist agent.
 */
export async function requestAgentAssistance(
  request: AssistRequest
): Promise<AssistResponse> {
  const response = await fetch(`${API_BASE_URL}/api/agent/assist`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(
      `Agent request failed: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}

/**
 * Check if agent is available.
 */
export async function checkAgentHealth(): Promise<{
  status: string;
  provider?: string;
  configured_providers?: Record<string, boolean>;
}> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/agent/health`);
    if (!response.ok) {
      return { status: "error" };
    }
    return response.json();
  } catch {
    return { status: "offline" };
  }
}
