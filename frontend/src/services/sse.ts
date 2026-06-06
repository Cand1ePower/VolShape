import EventSource, { EventSourceListener } from 'react-native-sse';

export interface ChatMessageRequest {
  user_input: string;
  session_id?: string;
  mode?: string;
  use_training_sheet?: boolean;
}

export interface SSEHandlers {
  onState?: (data: { node: string; message: string }) => void;
  onToken?: (text: string) => void;
  onUI?: (cardData: any) => void;
  onDone?: () => void;
  onError?: (error: any) => void;
  onOpen?: () => void;
}

/**
 * 发送聊天消息并建立 SSE 连接接收流式响应。
 * @param url 后端 SSE 接口地址
 * @param token 认证凭证 JWT Token
 * @param body 请求体 (ChatRequest)
 * @param handlers 事件回调处理器
 * @returns EventSource 实例，调用其 close() 可以手动中断连接
 */
export function connectChatStream(
  url: string,
  token: string,
  body: ChatMessageRequest,
  handlers: SSEHandlers
): EventSource {
  let errorDelivered = false;
  const eventSource = new EventSource(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const onOpenListener: EventSourceListener = (event) => {
    handlers.onOpen?.();
  };

  const parseErrorPayload = (event: any) => {
    if (event?.data) {
      try {
        return JSON.parse(event.data);
      } catch {}
    }
    if (event?.message) {
      try {
        const parsedMessage = JSON.parse(event.message);
        if (parsedMessage?.detail) {
          return {
            code: event.xhrStatus ? `http_${event.xhrStatus}` : 'sse_error',
            message: parsedMessage.detail,
            status: event.xhrStatus,
          };
        }
      } catch {}
    }
    return event;
  };

  const onErrorListener: EventSourceListener = (event: any) => {
    if (errorDelivered) {
      return;
    }
    errorDelivered = true;
    handlers.onError?.(parseErrorPayload(event));
    eventSource.close();
  };

  const onStateListener: EventSourceListener = (event: any) => {
    if (event.data) {
      try {
        const data = JSON.parse(event.data);
        handlers.onState?.(data);
      } catch (e) {
        console.error('Error parsing state event data:', e);
      }
    }
  };

  const onTokenListener: EventSourceListener = (event: any) => {
    if (event.data) {
      try {
        const data = JSON.parse(event.data);
        handlers.onToken?.(data.text);
      } catch (e) {
        console.error('Error parsing token event data:', e);
      }
    }
  };

  const onUIListener: EventSourceListener = (event: any) => {
    if (event.data) {
      try {
        const cardData = JSON.parse(event.data);
        handlers.onUI?.(cardData);
      } catch (e) {
        console.error('Error parsing UI event data:', e);
      }
    }
  };

  const onDoneListener: EventSourceListener = () => {
    handlers.onDone?.();
    eventSource.close();
  };

  // Catch-all message listener — works on native where named SSE events
  // (event: state / event: token) may not be parsed by react-native-sse
  const onMessageListener: EventSourceListener = (event: any) => {
    if (!event?.data) return;
    try {
      const payload = JSON.parse(event.data);
      // If payload has an "event" wrapper field, route to the appropriate handler
      if (payload.event) {
        switch (payload.event) {
          case 'state': handlers.onState?.(payload.data); break;
          case 'token': handlers.onToken?.(payload.data?.text || ''); break;
          case 'ui': handlers.onUI?.(payload.data); break;
          case 'done': handlers.onDone?.(); eventSource.close(); break;
          case 'error': handlers.onError?.(payload.data); break;
          default: break;
        }
        return;
      }
      // Fallback: try to detect legacy format
      if (payload.node) { handlers.onState?.(payload); return; }
      if (payload.text) { handlers.onToken?.(payload.text); return; }
      if (payload.type === 'workout_card' || payload.type === 'diet_card') { handlers.onUI?.(payload); return; }
    } catch {}
  };

  const esAny = eventSource as any;
  esAny.addEventListener('open', onOpenListener);
  esAny.addEventListener('error', onErrorListener);
  esAny.addEventListener('message', onMessageListener);  // catch-all
  // Named listeners as fallback for web
  esAny.addEventListener('state', onStateListener);
  esAny.addEventListener('token', onTokenListener);
  esAny.addEventListener('ui', onUIListener);
  esAny.addEventListener('done', onDoneListener);

  return eventSource;
}
