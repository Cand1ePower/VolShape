import { getBackendBaseUrl } from '@/services/api';
import { fetch as expoFetch } from 'expo/fetch';

export interface AnalyzeMediaParams {
  token: string;
  uri: string;
  name: string;
  mimeType: string;
  userInput: string;
  sessionId: string | null;
  onProgress?: (progress: number) => void;
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

export function analyzeMedia(params: AnalyzeMediaParams): Promise<AnalyzeMediaResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `${getBackendBaseUrl()}/api/media/analyze`;

    xhr.open('POST', url, true);
    xhr.setRequestHeader('Authorization', `Bearer ${params.token}`);

    xhr.upload.onprogress = (event) => {
      if (params.onProgress && event.lengthComputable) {
        params.onProgress(event.loaded / event.total);
      }
    };

    xhr.onload = () => {
      let payload;
      try {
        payload = JSON.parse(xhr.responseText);
      } catch (e) {
        payload = {};
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload as AnalyzeMediaResult);
      } else {
        reject(new Error(buildMediaError(payload?.detail ?? payload, xhr.status)));
      }
    };

    xhr.onerror = () => {
      reject(new Error('网络请求失败'));
    };

    const formData = new FormData();
    formData.append('file', {
      uri: params.uri,
      type: params.mimeType,
      name: params.name || 'media',
    } as any);
    
    formData.append('user_input', params.userInput);
    formData.append('mode', 'detailed');
    if (params.sessionId) {
      formData.append('session_id', params.sessionId);
    }

    xhr.send(formData);
  });
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
