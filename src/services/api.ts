// API Service - Connects to backend API
// Use relative URL '/api' in development to go through Vite proxy
// The proxy rewrites '/api/*' -> 'http://localhost:8000/*'
// Production: VITE_API_BASE_URL set via Render environment variables
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

import type { Tool, ToolDetail, AspectSentimentData } from "@/types/api";
import { toTool, toToolDetail } from "./entityTransformer";

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Fetch all entities (tools and LLMs)
 * Calls GET /entities (proxied through /api to backend)
 */
export async function fetchTools(): Promise<Tool[]> {
  try {
    const response = await fetch(`${BASE_URL}/entities`);

    if (!response.ok) {
      throw new Error(`Failed to fetch entities: ${response.status} ${response.statusText}`);
    }

    const entities = await response.json();
    // Transform backend entities to frontend Tool format
    return entities.map((entity: any) => toTool(entity));
  } catch (error) {
    console.error("Error fetching tools:", error);
    throw error;
  }
}

/**
 * Fetch entity details by ID
 * Calls GET /entities/{id} (proxied through /api to backend)
 */
export async function fetchToolDetail(id: string): Promise<ToolDetail | null> {
  try {
    const response = await fetch(`${BASE_URL}/entities/${id}`);

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      throw new Error(`Failed to fetch entity detail: ${response.status} ${response.statusText}`);
    }

    const entity = await response.json();
    // Transform backend entity to frontend ToolDetail format
    return toToolDetail(entity);
  } catch (error) {
    console.error("Error fetching tool detail:", error);
    throw error;
  }
}

/**
 * Fetch aspect-level sentiment for an entity
 * Calls GET /entities/{id}/aspects with window and optional source filter
 */
export async function fetchAspectSentiment(
  entityId: string,
  window: "7d" | "30d" | "90d" = "7d",
  source?: string
): Promise<AspectSentimentData> {
  try {
    const params = new URLSearchParams({ window });
    if (source && source !== "all") params.append("source", source);

    const response = await fetch(
      `${BASE_URL}/entities/${entityId}/aspects?${params}`
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch aspects: ${response.status} ${response.statusText}`);
    }

    const data: AspectSentimentData = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching aspect data:", error);
    throw error;
  }
}
