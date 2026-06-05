import { getBackendBaseUrl } from '@/services/api';
import { fetch as expoFetch } from 'expo/fetch';
import { File } from 'expo-file-system';

export interface AnalyzeMediaParams {
  token: string;
  uri: string;
  name: string;
  mimeType: string;
  userInput: string;
  sessionId: string | null;
}

export interface AnalyzeMediaResult {
  session_id: string;
  capability: 'nutrition_photo' | 'movement_video';
  final_response: string;
  card?: any;
  structured_result?: any;
}

export interface ConfirmPortionParams {
  token: string;
  sessionId: string | null;
  prompt: string;
  mealType: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  portionNote?: string;
  items: any[];
}

function buildMediaError(detail: unknown, status: number) {
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === 'object' && 'detail' in (detail as Record<string, unknown>)) {
    const nested = (detail as Record<string, unknown>).detail;
    if (typeof nested === 'string' && nested.trim()) {
      return nested;
    }
  }
  if (status === 403) {
    return '上传解析功能仅在专家模式下可用。';
  }
  return '媒体解析失败，请稍后再试。';
}

export async function analyzeMedia(params: AnalyzeMediaParams): Promise<AnalyzeMediaResult> {
  const formData = new FormData();
  formData.append('user_input', params.userInput);
  formData.append('mode', 'detailed');
  if (params.sessionId) {
    formData.append('session_id', params.sessionId);
  }
  const uploadFile = new File(params.uri);
  formData.append('file', uploadFile, params.name);

  const response = await expoFetch(`${getBackendBaseUrl()}/api/media/analyze`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${params.token}`,
    },
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(buildMediaError(payload?.detail ?? payload, response.status));
  }
  return payload as AnalyzeMediaResult;
}

export async function confirmPortion(params: ConfirmPortionParams): Promise<AnalyzeMediaResult> {
  const response = await fetch(`${getBackendBaseUrl()}/api/media/portion-confirm`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${params.token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: params.sessionId,
      prompt: params.prompt,
      meal_type: params.mealType,
      portion_note: params.portionNote || '',
      items: params.items,
    }),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(buildMediaError(payload?.detail ?? payload, response.status));
  }
  return payload as AnalyzeMediaResult;
}
