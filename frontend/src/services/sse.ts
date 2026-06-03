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

  const onErrorListener: EventSourceListener = (event: any) => {
    if (event?.data) {
      try {
        handlers.onError?.(JSON.parse(event.data));
        return;
      } catch {}
    }
    handlers.onError?.(event);
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

  // 绑定监听器，转换为 any 以绕过 strict typing
  const esAny = eventSource as any;
  esAny.addEventListener('open', onOpenListener);
  esAny.addEventListener('error', onErrorListener);
  esAny.addEventListener('state', onStateListener);
  esAny.addEventListener('token', onTokenListener);
  esAny.addEventListener('ui', onUIListener);
  esAny.addEventListener('done', onDoneListener);

  return eventSource;
}
