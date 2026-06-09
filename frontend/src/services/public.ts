import { apiFetch } from '@/services/api';

export interface PublicHealthResponse {
  status: string;
  checks: Record<string, string>;
}

export interface PublicRagHit {
  title: string;
  heading_path: string[];
  source_type: string;
  page_start?: number | null;
  page_end?: number | null;
  score: number;
  score_type: string;
  preview: string;
}

export interface PublicRagResponse {
  query: string;
  answer: string | null;
  llm_degraded: boolean;
  llm_error: string | null;
  retrieval_mode: string;
  hit_count: number;
  sources: string[];
  hits: PublicRagHit[];
}

export async function fetchPublicHealth() {
  const response = await apiFetch('/health');
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as PublicHealthResponse;
}

export async function runPublicRagTest(query: string) {
  const response = await apiFetch('/api/public/rag-test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  let payload: any = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || payload?.message || `HTTP ${response.status}`;
    const retryAfter =
      response.status === 429
        ? Number(detail?.retry_after_seconds || response.headers.get('Retry-After') || 0)
        : 0;
    const error = new Error(message) as Error & { retryAfter?: number; status?: number };
    error.retryAfter = retryAfter;
    error.status = response.status;
    throw error;
  }

  return payload as PublicRagResponse;
}
