import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
  Keyboard,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useColorScheme,
  useWindowDimensions,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Image as ExpoImage } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from 'expo-router';

import { WorkoutCard } from '../components/ui/WorkoutCard';
import { DietCard } from '../components/ui/DietCard';
import { PortionConfirmCard } from '../components/ui/PortionConfirmCard';
import { useAuth } from '../contexts/AuthContext';
import { usePlan } from '../contexts/PlanContext';
import { analyzeMedia, confirmPortion } from '../services/media';
import { connectChatStream } from '../services/sse';
import { getBackendBaseUrl } from '@/services/api';

interface Message {
  id: string;
  text: string;
  isBot: boolean;
  createdAt: Date;
  customCard?: any;
  attachment?: MessageAttachment;
}

interface MessageAttachment {
  uri?: string;
  name: string;
  mimeType?: string;
  kind: 'image' | 'video';
}

interface ConversationSessionMeta {
  id: string;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
  pinned_at?: string | null;
  is_pinned?: boolean;
  last_message_at?: string | null;
}

interface PendingAttachment {
  uri: string;
  name: string;
  mimeType: string;
  kind: 'image' | 'video';
}

const attachmentCardToMessageAttachment = (card?: any): MessageAttachment | undefined => {
  if (!card || card.type !== 'media_attachment') {
    return undefined;
  }
  return {
    kind: card.mediaKind === 'video' ? 'video' : 'image',
    name: card.fileName || 'media',
    mimeType: card.mimeType || undefined,
    uri: card.previewUri || undefined,
  };
};

const getBackendUrl = () => `${getBackendBaseUrl()}/api/chat/stream`;

const getAttachmentLabel = (attachment: PendingAttachment) =>
  `${attachment.kind === 'image' ? '图片' : '视频'} · ${attachment.name}`;

const WELCOME_TEXT = '你好，我是 VolShape AI 教练。告诉我你的训练目标、今天的需求，或者直接让我开始制定计划。';
const LOGIN_WELCOME_TEXT = '你好，我是 VolShape AI 教练。请先登录后再继续使用。';
const HISTORY_ERROR_TEXT = '你好，我是 VolShape AI 教练。当前聊天记录加载失败，请稍后重试。';

const CHAT_PROMPT_SUGGESTIONS = [
  '根据我的目标生成今天的训练计划',
  '这是我今天的晚饭，帮我估算热量和三大营养',
  '我昨天做了哪些训练，实际完成了多少组？',
];

function parseInlineBold(text: string) {
  const parts: Array<{ text: string; bold: boolean }> = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index), bold: false });
    }
    parts.push({ text: match[1], bold: true });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex), bold: false });
  }

  return parts.length ? parts : [{ text, bold: false }];
}

function renderFormattedMessage(
  text: string,
  options: {
    color: string;
    fontSize: number;
    lineHeight: number;
  }
) {
  const blocks = text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, blockIndex) => {
    const parts = parseInlineBold(block);
    return (
      <Text
        key={`block-${blockIndex}`}
        selectable
        style={[
          styles.messageText,
          blockIndex === 0 ? null : styles.messageParagraphText,
          {
            color: options.color,
            fontSize: options.fontSize,
            lineHeight: options.lineHeight,
          },
        ]}
      >
        {parts.map((part, partIndex) => (
          <Text key={`part-${blockIndex}-${partIndex}`} style={part.bold ? styles.messageBold : undefined}>
            {part.text}
          </Text>
        ))}
      </Text>
    );
  });
}

export default function ChatScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation();

  const dynamicFontSize = width < 375 ? 14 : 15;

  const { sessionId, isLoggedIn, isLoading, getValidToken, setSessionId } = useAuth();
  const { resetPlan, syncWorkoutOnLogin } = usePlan();

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [inputHeight, setInputHeight] = useState(42);
  const [agentStatus, setAgentStatus] = useState<{ node: string; message: string } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [mode, setMode] = useState<'quick' | 'detailed'>('quick');
  const [useTrainingSheet, setUseTrainingSheet] = useState(false);
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);
  const [processingMessage, setProcessingMessage] = useState('正在处理用户信息...');
  const [isTabBarHidden, setIsTabBarHidden] = useState(false);
  const [sessionList, setSessionList] = useState<ConversationSessionMeta[]>([]);
  const [isSessionModalVisible, setIsSessionModalVisible] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(false);
  const [menuSession, setMenuSession] = useState<ConversationSessionMeta | null>(null);
  const [pendingAttachment, setPendingAttachment] = useState<PendingAttachment | null>(null);
  const [portionSubmittingId, setPortionSubmittingId] = useState<string | null>(null);
  const [previewAttachment, setPreviewAttachment] = useState<MessageAttachment | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [isCompressing, setIsCompressing] = useState(false);

  const lastScrollY = useRef(0);
  const keyboardLift = useRef(new Animated.Value(0)).current;
  const tabBarTranslateAnim = useRef(new Animated.Value(0)).current;
  const sheetAnim = useRef(new Animated.Value(1)).current;
  const capsuleAnim = useRef(new Animated.Value(0)).current;
  const scrollViewRef = useRef<ScrollView>(null);
  const currentBotTextRef = useRef('');
  const esRef = useRef<any>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionIdRef = useRef<string | null>(sessionId);
  const historyRequestRef = useRef(0);
  const activeBotMessageIdRef = useRef<string | null>(null);
  const pendingTokenBufferRef = useRef('');
  const pendingStreamDoneRef = useRef(false);
  const tokenFlushTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const floatingBaseBottom = Platform.OS === 'ios' ? 80 : 62;
  const keyboardGap = Platform.OS === 'ios' ? 8 : 42;

  const bgCol = isDark ? '#0A0A0C' : '#F5F5F7';
  const borderCol = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
  const textCol = isDark ? '#FFFFFF' : '#111827';
  const subTextCol = isDark ? '#A1A1AA' : '#6B7280';
  const botBubbleBg = isDark ? 'rgba(24, 24, 28, 0.78)' : 'rgba(255, 255, 255, 0.9)';
  const frostedBg = isDark ? 'rgba(18, 18, 22, 0.9)' : 'rgba(255, 255, 255, 0.92)';
  const inputLineHeight = dynamicFontSize + 6;
  const inputMinHeight = 42;
  const inputMaxHeight = inputLineHeight * 5;
  const currentSessionTitle = useMemo(
    () => sessionList.find((session) => session.id === sessionId)?.title || '新的对话',
    [sessionId, sessionList]
  );
  const visibleSessionList = useMemo(() => {
    if (!sessionId || sessionList.some((session) => session.id === sessionId)) {
      return sessionList;
    }
    return [{ id: sessionId, title: currentSessionTitle }, ...sessionList];
  }, [currentSessionTitle, sessionId, sessionList]);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const scrollToBottom = useCallback((animated = true) => {
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated });
    }, 80);
  }, []);

  const stopTokenFlush = useCallback(() => {
    if (tokenFlushTimerRef.current) {
      clearInterval(tokenFlushTimerRef.current);
      tokenFlushTimerRef.current = null;
    }
  }, []);

  const showWelcomeMessage = useCallback((text: string) => {
    setMessages([
      {
        id: 'welcome',
        text,
        isBot: true,
        createdAt: new Date(),
      },
    ]);
  }, []);

  const animateKeyboardLift = useCallback(
    (toValue: number, duration = 240) => {
      keyboardLift.stopAnimation();
      Animated.timing(keyboardLift, {
        toValue,
        duration,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }).start();
    },
    [keyboardLift]
  );

  const formatProcessingMessage = useCallback((state?: { node?: string; message?: string }) => {
    const text = `${state?.node || ''} ${state?.message || ''}`.toLowerCase();
    if (text.includes('intent')) return '正在分析用户意图...';
    if (text.includes('memory') || text.includes('profile')) return '正在同步用户记忆...';
    if (text.includes('knowledge') || text.includes('retrieval')) return '正在检索知识库...';
    if (text.includes('plan') || text.includes('workout')) return '正在制作计划...';
    if (text.includes('diet') || text.includes('nutrition')) return '正在整理饮食建议...';
    if (text.includes('response') || text.includes('final')) return '正在生成回复...';
    return '正在处理用户信息...';
  }, []);

  const refreshSessions = useCallback(async () => {
    if (!isLoggedIn) {
      return;
    }
    try {
      setIsSessionLoading(true);
      const validToken = await getValidToken();
      if (!validToken) {
        return;
      }
      const response = await fetch(`${getBackendBaseUrl()}/api/chat/sessions`, {
        headers: { Authorization: `Bearer ${validToken}` },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      const sessions: ConversationSessionMeta[] = data.sessions || [];
      setSessionList((prev) => (sessions.length > 0 ? sessions : prev));
      const resolvedSessionId =
        sessions.find((session) => session.id === sessionIdRef.current)?.id ||
        data.active_session_id ||
        sessions[0]?.id ||
        null;
      if (resolvedSessionId && resolvedSessionId !== sessionIdRef.current) {
        await setSessionId(resolvedSessionId);
      }
    } catch (error) {
      console.error('[Sessions] Load failed:', error);
    } finally {
      setIsSessionLoading(false);
    }
  }, [getValidToken, isLoggedIn, setSessionId]);

  const finalizeVisibleStream = useCallback(() => {
    pendingStreamDoneRef.current = false;
    setIsGenerating(false);
    setAgentStatus(null);
    refreshSessions();
    scrollToBottom(true);
  }, [refreshSessions, scrollToBottom]);

  const resetTokenStreamingState = useCallback(() => {
    stopTokenFlush();
    activeBotMessageIdRef.current = null;
    pendingTokenBufferRef.current = '';
    pendingStreamDoneRef.current = false;
    currentBotTextRef.current = '';
  }, [stopTokenFlush]);

  const ensureTokenFlush = useCallback(
    (botMessageId: string) => {
      activeBotMessageIdRef.current = botMessageId;
      if (tokenFlushTimerRef.current) {
        return;
      }

      tokenFlushTimerRef.current = setInterval(() => {
        const activeMessageId = activeBotMessageIdRef.current;
        if (!activeMessageId) {
          stopTokenFlush();
          return;
        }

        if (!pendingTokenBufferRef.current) {
          if (pendingStreamDoneRef.current) {
            stopTokenFlush();
            finalizeVisibleStream();
          }
          return;
        }

        const nextSlice = pendingTokenBufferRef.current.slice(0, 4);
        pendingTokenBufferRef.current = pendingTokenBufferRef.current.slice(4);
        currentBotTextRef.current += nextSlice;

        setMessages((prev) =>
          prev.map((msg) => (msg.id === activeMessageId ? { ...msg, text: currentBotTextRef.current } : msg))
        );
        scrollToBottom(false);

        if (!pendingTokenBufferRef.current && pendingStreamDoneRef.current) {
          stopTokenFlush();
          finalizeVisibleStream();
        }
      }, 28);
    },
    [finalizeVisibleStream, scrollToBottom, stopTokenFlush]
  );

  useEffect(() => {
    return () => {
      stopTokenFlush();
    };
  }, [stopTokenFlush]);

  const handleOpenSessionModal = useCallback(() => {
    setIsSessionModalVisible(true);
    refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (isSessionModalVisible && isLoggedIn) {
      refreshSessions();
    }
  }, [isLoggedIn, isSessionModalVisible, refreshSessions]);

  const handleCreateSession = useCallback(async () => {
    try {
      const validToken = await getValidToken();
      if (!validToken) {
        return;
      }
      const response = await fetch(`${getBackendBaseUrl()}/api/chat/sessions`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${validToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      const createdSession = data.session as ConversationSessionMeta;
      setSessionList((prev) => [createdSession, ...prev.filter((session) => session.id !== createdSession.id)]);
      await setSessionId(createdSession.id);
      sessionIdRef.current = createdSession.id;
      await refreshSessions();
      setIsSessionModalVisible(false);
      setMessages([]);
      setAgentStatus(null);
    } catch (error) {
      console.error('[Sessions] Create failed:', error);
    }
  }, [getValidToken, refreshSessions, setSessionId]);

  const handleSelectSession = useCallback(
    async (nextSessionId: string) => {
      if (nextSessionId === sessionId) {
        setIsSessionModalVisible(false);
        return;
      }
      await setSessionId(nextSessionId);
      setMessages([]);
      setAgentStatus(null);
      setIsSessionModalVisible(false);
    },
    [sessionId, setSessionId]
  );

  const handleTogglePinSession = useCallback(async () => {
    if (!menuSession) return;
    try {
      const validToken = await getValidToken();
      if (!validToken) {
        return;
      }
      const response = await fetch(`${getBackendBaseUrl()}/api/chat/sessions/${menuSession.id}`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${validToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pinned: !menuSession.is_pinned }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      setMenuSession(null);
      await refreshSessions();
    } catch (error) {
      console.error('[Sessions] Pin failed:', error);
    }
  }, [getValidToken, menuSession, refreshSessions]);

  const handleDeleteSession = useCallback(async () => {
    if (!menuSession) return;
    try {
      const validToken = await getValidToken();
      if (!validToken) {
        return;
      }
      const response = await fetch(`${getBackendBaseUrl()}/api/chat/sessions/${menuSession.id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${validToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      const sessions: ConversationSessionMeta[] = data.sessions || [];
      const deletedSessionId = menuSession.id;
      const nextSessionId =
        deletedSessionId === sessionId ? data.active_session_id || sessions[0]?.id || null : sessionId;

      setSessionList(sessions);
      setMenuSession(null);

      if (nextSessionId !== sessionId) {
        await setSessionId(nextSessionId);
        sessionIdRef.current = nextSessionId;
        setMessages([]);
        setAgentStatus(null);
      }
    } catch (error) {
      console.error('[Sessions] Delete failed:', error);
    }
  }, [getValidToken, menuSession, sessionId, setSessionId]);

  const handleModeChange = useCallback(
    (newMode: 'quick' | 'detailed') => {
      setMode(newMode);
      Animated.timing(capsuleAnim, {
        toValue: newMode === 'quick' ? 0 : 1,
        duration: 220,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: false,
      }).start();

      if (newMode === 'detailed') {
        setUseTrainingSheet(true);
        Animated.timing(sheetAnim, {
          toValue: 0,
          duration: 220,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: false,
        }).start();
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          Animated.timing(sheetAnim, {
            toValue: 1,
            duration: 250,
            easing: Easing.out(Easing.cubic),
            useNativeDriver: false,
          }).start();
        }, 2000);
      } else {
        setUseTrainingSheet(false);
        setPendingAttachment(null);
        Animated.timing(sheetAnim, {
          toValue: 1,
          duration: 250,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: false,
        }).start();
      }
    },
    [capsuleAnim, sheetAnim]
  );

  const handlePickAttachment = useCallback(async () => {
    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('无法访问相册', '请先允许 VolShape 访问你的媒体库。');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images', 'videos'] as any,
        allowsEditing: false,
        quality: 0.9,
      });

      if (result.canceled || !result.assets?.length) {
        return;
      }

      const asset = result.assets[0];
      const kind: 'image' | 'video' = asset.type === 'video' ? 'video' : 'image';
      const fallbackName = `${kind}-${Date.now()}${kind === 'image' ? '.jpg' : '.mp4'}`;
      const derivedName = asset.fileName || asset.uri.split('/').pop()?.split('?')[0] || fallbackName;
      const mimeType = asset.mimeType || (kind === 'image' ? 'image/jpeg' : 'video/mp4');

      setPendingAttachment({
        uri: asset.uri,
        name: derivedName,
        mimeType,
        kind,
      });
    } catch (error) {
      console.error('[Media] Pick failed:', error);
      Alert.alert('选择失败', '暂时无法读取这份媒体文件，请稍后再试。');
    }
  }, []);

  const handleConfirmPortion = useCallback(
    async (messageId: string, cardData: any, items: any[]) => {
      try {
        setPortionSubmittingId(messageId);
        const validToken = await getValidToken();
        if (!validToken) {
          throw new Error('请先登录后再继续使用 AI 教练。');
        }

        const result = await confirmPortion({
          token: validToken,
          sessionId: sessionIdRef.current,
          prompt: cardData.prompt,
          mealType: cardData.mealType,
          portionNote: cardData.portionNote,
          items,
        });

        if (result.session_id && result.session_id !== sessionIdRef.current) {
          await setSessionId(result.session_id);
          sessionIdRef.current = result.session_id;
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === messageId ? { ...msg, text: result.final_response, customCard: result.card } : msg
          )
        );
        refreshSessions();
        scrollToBottom(true);
      } catch (error: any) {
        const message = error?.message || '确认分量失败，请稍后再试。';
        setMessages((prev) =>
          prev.map((msg) => (msg.id === messageId ? { ...msg, text: `鈿狅笍 ${message}` } : msg))
        );
      } finally {
        setPortionSubmittingId(null);
      }
    },
    [getValidToken, refreshSessions, scrollToBottom, setSessionId]
  );

  const handleConfirmDietRecord = useCallback(
    async (messageId: string) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId && msg.customCard?.type === 'diet_card'
            ? {
                ...msg,
                customCard: {
                  ...msg.customCard,
                  confirmed: true,
                },
              }
            : msg
        )
      );
      refreshSessions();
    },
    [refreshSessions]
  );

  const handleToggleSheet = useCallback(() => {
    setUseTrainingSheet((prev) => !prev);
    if (timerRef.current) clearTimeout(timerRef.current);
    Animated.timing(sheetAnim, {
      toValue: 0,
      duration: 220,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
    timerRef.current = setTimeout(() => {
      Animated.timing(sheetAnim, {
        toValue: 1,
        duration: 250,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: false,
      }).start();
    }, 1000);
  }, [sheetAnim]);

  const handleInputContentSizeChange = useCallback(
    (event: any) => {
      const contentHeight = Math.ceil(event?.nativeEvent?.contentSize?.height || inputMinHeight);
      setInputHeight(Math.max(inputMinHeight, Math.min(inputMaxHeight, contentHeight)));
    },
    [inputMaxHeight, inputMinHeight]
  );

  const handleScroll = useCallback(
    (event: any) => {
      if (isKeyboardVisible) return;
      const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
      const currentY = contentOffset.y;
      const delta = currentY - lastScrollY.current;
      const isAtBottom = layoutMeasurement.height + currentY >= contentSize.height - 40;

      if (isAtBottom || currentY < 50) {
        if (isTabBarHidden) setIsTabBarHidden(false);
        lastScrollY.current = currentY;
        return;
      }

      if (Math.abs(delta) < 6) return;
      if (delta > 0) {
        if (isTabBarHidden) setIsTabBarHidden(false);
      } else if (!isTabBarHidden) {
        setIsTabBarHidden(true);
      }
      lastScrollY.current = currentY;
    },
    [isKeyboardVisible, isTabBarHidden]
  );

  const handleSend = useCallback(async () => {
    if ((!inputText.trim() && !pendingAttachment) || isGenerating) return;
    if (!sessionId) {
      await refreshSessions();
      return;
    }

    const userText = inputText.trim();
    const attachment = pendingAttachment;
    const localMessageId = Math.random().toString(36).slice(2);
    setInputText('');
    setInputHeight(inputMinHeight);
    setPendingAttachment(null);
    setMessages((prev) => [
      ...prev,
      {
        id: localMessageId,
        text: userText,
        isBot: false,
        createdAt: new Date(),
        attachment: attachment || undefined,
      },
    ]);
    scrollToBottom(true);

    const validToken = await getValidToken();
    if (!validToken) {
      const botMessageId = Math.random().toString(36).slice(2);
      setMessages((prev) => [...prev, { id: botMessageId, text: '请先登录后再继续使用 AI 教练。', isBot: true, createdAt: new Date() }]);
      return;
    }

    if (attachment) {
      try {
        let finalUri = attachment.uri;


        setIsGenerating(true);
        setUploadProgress(0);

        const result = await analyzeMedia({
          token: validToken,
          uri: finalUri,
          name: attachment.name,
          mimeType: attachment.mimeType,
          userInput: userText,
          sessionId,
          onProgress: (p) => setUploadProgress(p)
        });

        setUploadProgress(null);

        const botMessageId = Math.random().toString(36).slice(2);
        setMessages((prev) => [...prev, { id: botMessageId, text: '', isBot: true, createdAt: new Date() }]);
        currentBotTextRef.current = '';

        setAgentStatus({ node: 'Media Parser', message: '解析完成' });
        setProcessingMessage(formatProcessingMessage({ node: 'Media Parser', message: '解析完成' }));

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === botMessageId
              ? {
                  ...msg,
                  text: result.final_response,
                  customCard: result.card,
                }
              : msg
          )
        );
        refreshSessions();
      } catch (error: any) {
        setIsCompressing(false);
        setUploadProgress(null);
        setIsGenerating(false);
        
        const botMessageId = Math.random().toString(36).slice(2);
        setMessages((prev) => [...prev, { id: botMessageId, text: '', isBot: true, createdAt: new Date() }]);
        
        const message = error?.message || '媒体解析失败，请稍后再试。';
        setMessages((prev) =>
          prev.map((msg) => (msg.id === botMessageId ? { ...msg, text: `⚠️ ${message}` } : msg))
        );
        scrollToBottom();
      } finally {
        setIsGenerating(false);
        setAgentStatus(null);
      }
      return;
    }

    // Normal text message flow
    setIsGenerating(true);
    const initialStatus = { node: 'Intent Classifier', message: '正在分析用户意图...' };
    setAgentStatus(initialStatus);
    setProcessingMessage(formatProcessingMessage(initialStatus));

    const botMessageId = Math.random().toString(36).slice(2);
    setMessages((prev) => [...prev, { id: botMessageId, text: '', isBot: true, createdAt: new Date() }]);
    resetTokenStreamingState();
    activeBotMessageIdRef.current = botMessageId;

    try {
      esRef.current?.close?.();
      esRef.current = connectChatStream(
        getBackendUrl(),
        validToken,
        {
          user_input: userText,
          session_id: sessionId,
          mode,
          use_training_sheet: useTrainingSheet,
        },
        {
          onState: (state) => {
            setAgentStatus(state);
            setProcessingMessage(formatProcessingMessage(state));
            scrollToBottom(true);
          },
          onToken: (tokenText) => {
            pendingTokenBufferRef.current += tokenText;
            ensureTokenFlush(botMessageId);
          },
          onUI: (cardData) => {
            setMessages((prev) =>
              prev.map((msg) => (msg.id === botMessageId ? { ...msg, customCard: cardData } : msg))
            );
            scrollToBottom(true);
          },
          onDone: () => {
            pendingStreamDoneRef.current = true;
            if (!pendingTokenBufferRef.current) {
              finalizeVisibleStream();
            }
          },
          onError: (err) => {
            resetTokenStreamingState();
            setIsGenerating(false);
            setAgentStatus(null);
            esRef.current?.close?.();
            const message = err?.message || '????????????????????????';
            const suffix = err?.code ? `\n\n????${err.code}` : '';
            setMessages((prev) =>
              prev.map((msg) => (msg.id === botMessageId ? { ...msg, text: `?? ${message}${suffix}` } : msg))
            );
            scrollToBottom(true);
          },
        }
      );
    } catch (error: any) {
      resetTokenStreamingState();
      setIsGenerating(false);
      setAgentStatus(null);
      const message = error?.message || '???????????';
      setMessages((prev) =>
        prev.map((msg) => (msg.id === botMessageId ? { ...msg, text: `?? ${message}` } : msg))
      );
    }
  }, [ensureTokenFlush, finalizeVisibleStream, formatProcessingMessage, getValidToken, inputMinHeight, inputText, isGenerating, mode, pendingAttachment, refreshSessions, resetTokenStreamingState, scrollToBottom, sessionId, useTrainingSheet]);
  useEffect(() => {
    if (!isLoggedIn) {
      resetPlan();
      setMessages([]);
      setAgentStatus(null);
      setSessionList([]);
      setIsSessionModalVisible(false);
      return;
    }
    syncWorkoutOnLogin();
  }, [isLoggedIn, resetPlan, syncWorkoutOnLogin]);

  useEffect(() => {
    navigation.setOptions({
      tabBarStyle: {
        backgroundColor: isDark ? 'rgba(20, 20, 26, 0.85)' : 'rgba(255, 255, 255, 0.88)',
        borderTopWidth: 0.5,
        borderTopColor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
        shadowColor: 'transparent',
        elevation: 0,
        paddingBottom: Platform.OS === 'ios' ? 22 : 8,
        paddingTop: 8,
        height: Platform.OS === 'ios' ? 76 : 58,
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        transform: [{ translateY: tabBarTranslateAnim }],
        ...(Platform.OS === 'web'
          ? ({ backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } as any)
          : {}),
      },
    });
  }, [isDark, navigation, tabBarTranslateAnim]);

  useEffect(() => {
    Animated.timing(tabBarTranslateAnim, {
      toValue: isTabBarHidden ? 100 : 0,
      duration: 300,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [isTabBarHidden, tabBarTranslateAnim]);

  useEffect(() => {
    const showSubscription = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      (event) => {
        setIsKeyboardVisible(true);
        setIsTabBarHidden(false);
        const safeBottom = Platform.OS === 'ios' ? insets.bottom : 0;
        const keyboardHeight = Math.max(0, event.endCoordinates.height - safeBottom);
        animateKeyboardLift(Math.max(0, keyboardHeight - floatingBaseBottom + keyboardGap), event.duration || 240);
      }
    );

    const hideSubscription = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide',
      (event) => {
        setIsKeyboardVisible(false);
        animateKeyboardLift(0, event.duration || 220);
      }
    );

    return () => {
      showSubscription.remove();
      hideSubscription.remove();
    };
  }, [animateKeyboardLift, floatingBaseBottom, insets.bottom, keyboardGap]);

  useEffect(() => {
    if (!isLoading && isLoggedIn) {
      refreshSessions();
    }
  }, [isLoading, isLoggedIn, refreshSessions]);

  useEffect(() => {
    if (isLoading) return;
    if (!isLoggedIn) {
      setMessages([]);
      return;
    }
    if (!sessionId) return;

    (async () => {
      const requestId = ++historyRequestRef.current;
      const targetSessionId = sessionId;
      try {
        const validToken = await getValidToken();
        if (!validToken) {
          if (historyRequestRef.current !== requestId || sessionIdRef.current !== targetSessionId) return;
          showWelcomeMessage(LOGIN_WELCOME_TEXT);
          return;
        }
        const response = await fetch(
          `${getBackendBaseUrl()}/api/chat/history?session_id=${encodeURIComponent(targetSessionId)}&limit=50`,
          {
            headers: { Authorization: `Bearer ${validToken}` },
          }
        );
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        if (historyRequestRef.current !== requestId || sessionIdRef.current !== targetSessionId) {
          return;
        }
        if (!data.messages?.length) {
          showWelcomeMessage(WELCOME_TEXT);
          return;
        }
        setMessages(
          data.messages.map((message: any, index: number) => {
            const attachment = attachmentCardToMessageAttachment(message.customCard);
            return {
              id: `hist-${message.created_at || index}`,
              text: message.content,
              isBot: message.role === 'assistant',
              createdAt: message.created_at ? new Date(message.created_at) : new Date(),
              customCard: attachment ? undefined : message.customCard || undefined,
              attachment,
            };
          })
        );
      } catch (error) {
        if (historyRequestRef.current !== requestId || sessionIdRef.current !== targetSessionId) {
          return;
        }
        console.error('[History] Load failed:', error);
        showWelcomeMessage(HISTORY_ERROR_TEXT);
      }
    })();
  }, [getValidToken, isLoading, isLoggedIn, sessionId, showWelcomeMessage]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (esRef.current) esRef.current.close();
    };
  }, []);

  return (
    <View style={[styles.container, { backgroundColor: bgCol }]}>
      <LinearGradient
        colors={[
          isDark ? 'rgba(10,10,12,0.96)' : 'rgba(245,245,247,0.96)',
          isDark ? 'rgba(10,10,12,0)' : 'rgba(245,245,247,0)',
        ]}
        style={[styles.header, { paddingTop: Math.max(insets.top, 12), paddingBottom: 24 }]}
      >
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={[styles.headerTitle, { color: textCol }]}>VolShape</Text>
            <View style={styles.headerSubtitleRow}>
              <View style={[styles.statusDot, { backgroundColor: isGenerating ? '#34C759' : isLoggedIn ? '#007AFF' : '#AEAEB2' }]} />
              <Text style={[styles.headerSubtitle, { color: subTextCol }]} numberOfLines={1}>
                {isGenerating ? '处理中' : isLoggedIn ? currentSessionTitle : '未登录'}
              </Text>
            </View>
          </View>
          <View style={styles.headerRight}>
            <TouchableOpacity
              style={[styles.headerIconButton, { backgroundColor: frostedBg, borderColor: borderCol }]}
              onPress={handleCreateSession}
              disabled={!isLoggedIn}
            >
              <Ionicons name="add" size={18} color={isLoggedIn ? textCol : subTextCol} />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.headerIconButton, { backgroundColor: frostedBg, borderColor: borderCol }]}
              onPress={handleOpenSessionModal}
              disabled={!isLoggedIn}
            >
              <Ionicons name="layers-outline" size={17} color={isLoggedIn ? textCol : subTextCol} />
            </TouchableOpacity>
          </View>
        </View>
      </LinearGradient>

      {agentStatus && (
        <View
          style={[
            styles.statusBanner,
            {
              backgroundColor: isDark ? 'rgba(0,122,255,0.08)' : 'rgba(0,122,255,0.04)',
              borderBottomColor: borderCol,
            },
          ]}
        >
          <View style={styles.statusInner}>
            <ActivityIndicator size="small" color="#007AFF" style={styles.spinner} />
            <Text style={[styles.statusMessage, { color: subTextCol }]} numberOfLines={1}>
              {processingMessage}
            </Text>
          </View>
        </View>
      )}

      <ScrollView
        ref={scrollViewRef}
        style={styles.chatScroll}
        contentContainerStyle={styles.chatContent}
        scrollEventThrottle={16}
        onScroll={handleScroll}
        onContentSizeChange={() => scrollToBottom(true)}
      >
        <View style={styles.chatMaxWidth}>
          {(messages.length === 0 || (messages.length === 1 && messages[0]?.id === 'welcome')) && (
            <View
              style={[
                styles.emptyChatHero,
                {
                  backgroundColor: botBubbleBg,
                  borderColor: borderCol,
                },
              ]}
            >
              <Text style={[styles.emptyChatEyebrow, { color: subTextCol }]}>VOLSHAPE COACH</Text>
              <Text style={[styles.emptyChatTitle, { color: textCol }]}>从一句话开始今天的训练或饮食记录</Text>
              <Text style={[styles.emptyChatDescription, { color: subTextCol }]}>
                你可以直接提训练目标、恢复状态、饮食照片，或者追问昨天的训练完成情况。专家模式下也支持图片与视频分析。
              </Text>
              <View style={styles.emptyChatSuggestionList}>
                {CHAT_PROMPT_SUGGESTIONS.map((suggestion) => (
                  <TouchableOpacity
                    key={suggestion}
                    activeOpacity={0.82}
                    style={[
                      styles.emptyChatSuggestion,
                      {
                        backgroundColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)',
                        borderColor: borderCol,
                      },
                    ]}
                    onPress={() => setInputText(suggestion)}
                  >
                    <Text style={[styles.emptyChatSuggestionText, { color: textCol }]}>{suggestion}</Text>
                    <Ionicons name="arrow-up-outline" size={16} color={subTextCol} />
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}
          {messages.map((msg, index) => {
            const isStreamingPlaceholder = isGenerating && msg.isBot && messages[messages.length - 1]?.id === msg.id && !msg.text;
            return (
              <View
                key={`${msg.id}-${index}`}
                style={[styles.messageRow, msg.isBot ? styles.botRow : styles.userRow]}
              >
                <View
                  style={[
                    styles.bubble,
                    msg.isBot
                      ? [
                          styles.botBubble,
                          {
                            backgroundColor: botBubbleBg,
                            borderColor: borderCol,
                          },
                        ]
                      : styles.userBubble,
                  ]}
                >
                  {msg.attachment && (
                    <TouchableOpacity
                      activeOpacity={0.88}
                      style={[
                        styles.messageAttachment,
                        {
                          backgroundColor: msg.isBot ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.16)',
                          borderColor: msg.isBot ? borderCol : 'rgba(255,255,255,0.18)',
                        },
                      ]}
                      onPress={() => msg.attachment && setPreviewAttachment(msg.attachment)}
                    >
                      {msg.attachment.kind === 'image' && msg.attachment.uri ? (
                        <ExpoImage source={{ uri: msg.attachment.uri }} style={styles.messageAttachmentThumb} contentFit="cover" />
                      ) : (
                        <View style={styles.messageAttachmentIcon}>
                          <Ionicons
                            name={msg.attachment.kind === 'image' ? 'image-outline' : 'videocam-outline'}
                            size={16}
                            color={msg.isBot ? subTextCol : '#FFFFFF'}
                          />
                        </View>
                      )}
                    </TouchableOpacity>
                  )}

                  {msg.text ? (
                    <View>
                      {renderFormattedMessage(msg.text, {
                        color: msg.isBot ? textCol : '#FFFFFF',
                        fontSize: dynamicFontSize,
                        lineHeight: dynamicFontSize + 7,
                      })}
                    </View>
                  ) : isStreamingPlaceholder ? (
                    <View style={styles.processingLine}>
                      <ActivityIndicator size="small" color="#007AFF" style={{ marginRight: 8 }} />
                      <Text style={[styles.processingText, { color: subTextCol }]} numberOfLines={1}>
                        {processingMessage}
                      </Text>
                    </View>
                  ) : null}

                  {msg.customCard && (
                    <View style={styles.cardContainer}>
                    {msg.customCard.type === 'workout_card' ? (
                      <WorkoutCard data={msg.customCard} />
                    ) : msg.customCard.type === 'diet_card' ? (
                      <DietCard
                        data={msg.customCard}
                        onConfirm={() => handleConfirmDietRecord(msg.id)}
                      />
                    ) : msg.customCard.type === 'portion_confirm_card' ? (
                      <PortionConfirmCard
                        data={msg.customCard}
                          loading={portionSubmittingId === msg.id}
                          onConfirm={(items) => handleConfirmPortion(msg.id, msg.customCard, items)}
                        />
                      ) : null}
                    </View>
                  )}
                </View>
              </View>
            );
          })}
        </View>
      </ScrollView>

      <Animated.View
        style={[
          styles.floatingControls,
          {
            bottom: floatingBaseBottom,
            transform: [
              {
                translateY: tabBarTranslateAnim.interpolate({
                  inputRange: [0, 100],
                  outputRange: [0, isKeyboardVisible ? 0 : 48],
                }),
              },
              {
                translateY: keyboardLift.interpolate({
                  inputRange: [0, 1000],
                  outputRange: [0, -1000],
                  extrapolate: 'clamp',
                }),
              },
            ],
          },
        ]}
      >
        {!isKeyboardVisible && (
          <View style={styles.controlBar}>
            <View
              style={[
                styles.modeCapsule,
                {
                  backgroundColor: frostedBg,
                  borderColor: borderCol,
                },
              ]}
            >
              <Animated.View
                style={[
                  styles.capsuleSlider,
                  { left: capsuleAnim.interpolate({ inputRange: [0, 1], outputRange: [2, 46] }) },
                ]}
              />
              <TouchableOpacity style={styles.capsuleOption} onPress={() => handleModeChange('quick')} activeOpacity={0.85}>
                <Text style={[styles.capsuleText, { color: mode === 'quick' ? '#FFFFFF' : subTextCol }]}>快速</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.capsuleOption}
                onPress={() => handleModeChange('detailed')}
                activeOpacity={0.85}
              >
                <Text style={[styles.capsuleText, { color: mode === 'detailed' ? '#FFFFFF' : subTextCol }]}>专家</Text>
              </TouchableOpacity>
            </View>

            <Animated.View
              style={[
                styles.sheetButtonShell,
                {
                  width: sheetAnim.interpolate({ inputRange: [0, 1], outputRange: [76, 28] }),
                  backgroundColor: useTrainingSheet ? '#007AFF' : frostedBg,
                  borderColor: useTrainingSheet ? '#007AFF' : borderCol,
                },
              ]}
            >
              <TouchableOpacity style={styles.sheetButtonInner} onPress={handleToggleSheet} activeOpacity={0.8}>
                <Ionicons
                  name="list-outline"
                  size={14}
                  color={useTrainingSheet ? '#FFFFFF' : subTextCol}
                />
                <Animated.Text
                  numberOfLines={1}
                  style={[
                    styles.sheetButtonText,
                    {
                      color: useTrainingSheet ? '#FFFFFF' : subTextCol,
                      opacity: sheetAnim.interpolate({ inputRange: [0, 0.4, 1], outputRange: [1, 0, 0] }),
                      maxWidth: sheetAnim.interpolate({ inputRange: [0, 1], outputRange: [42, 0] }),
                      marginLeft: sheetAnim.interpolate({ inputRange: [0, 1], outputRange: [4, 0] }),
                    },
                  ]}
                >
                  训练表                </Animated.Text>
              </TouchableOpacity>
            </Animated.View>
          </View>
        )}

        {(isCompressing || uploadProgress !== null) && (
          <View
            style={[
              styles.pendingAttachmentBar,
              {
                backgroundColor: isDark ? 'rgba(30, 30, 36, 0.85)' : 'rgba(255, 255, 255, 0.95)',
                borderColor: borderCol,
                paddingVertical: 12,
              },
            ]}
          >
            <View style={[styles.pendingAttachmentTextWrap, { marginLeft: 8 }]}>
              <Text style={[styles.pendingAttachmentTitle, { color: textCol, marginBottom: 6 }]}>
                {isCompressing ? '正在压缩视频以节省流量...' : `正在上传... ${Math.round((uploadProgress || 0) * 100)}%`}
              </Text>
              {uploadProgress !== null && (
                <View style={{ width: '100%', height: 4, backgroundColor: isDark ? '#333' : '#E5E5EA', borderRadius: 2, overflow: 'hidden' }}>
                  <View style={{ width: `${Math.round(uploadProgress * 100)}%`, height: '100%', backgroundColor: '#007AFF' }} />
                </View>
              )}
            </View>
          </View>
        )}

        {pendingAttachment && (
          <View
            style={[
              styles.pendingAttachmentBar,
              {
                backgroundColor: frostedBg,
                borderColor: borderCol,
              },
            ]}
          >
            <TouchableOpacity
              activeOpacity={0.85}
              style={styles.pendingAttachmentMain}
              onPress={() => setPreviewAttachment(pendingAttachment)}
            >
              {pendingAttachment.kind === 'image' ? (
                <ExpoImage
                  source={{ uri: pendingAttachment.uri }}
                  style={styles.pendingAttachmentThumb}
                  contentFit="cover"
                />
              ) : (
                <View style={styles.pendingAttachmentIcon}>
                  <Ionicons name="videocam-outline" size={16} color={subTextCol} />
                </View>
              )}
              <View style={styles.pendingAttachmentTextWrap}>
                <Text style={[styles.pendingAttachmentTitle, { color: textCol }]}>
                  {pendingAttachment.kind === 'image' ? '已选择图片' : '已选择视频'}
                </Text>
                <Text style={[styles.pendingAttachmentSubtitle, { color: subTextCol }]} numberOfLines={1}>
                  {pendingAttachment.name}
                </Text>
              </View>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.85}
              style={styles.pendingAttachmentClose}
              onPress={() => setPendingAttachment(null)}
            >
              <Ionicons name="close" size={16} color={subTextCol} />
            </TouchableOpacity>
          </View>
        )}

        <View
          style={[
            styles.floatingInput,
            {
              backgroundColor: frostedBg,
              borderColor: isDark ? 'rgba(0,122,255,0.22)' : 'rgba(0,122,255,0.14)',
            },
          ]}
        >
          {mode === 'detailed' && (
            <TouchableOpacity
              activeOpacity={0.85}
              disabled={isGenerating}
              style={[
                styles.attachButton,
                {
                  backgroundColor: pendingAttachment
                    ? 'rgba(0,122,255,0.16)'
                    : isDark
                      ? 'rgba(255,255,255,0.06)'
                      : 'rgba(0,0,0,0.04)',
                },
              ]}
              onPress={handlePickAttachment}
            >
              <Ionicons
                name={pendingAttachment ? 'document-attach' : 'add-circle-outline'}
                size={18}
                color={pendingAttachment ? '#007AFF' : subTextCol}
              />
            </TouchableOpacity>
          )}
          <TextInput
            style={[
              styles.textInput,
              {
                color: textCol,
                fontSize: dynamicFontSize,
                lineHeight: inputLineHeight,
                height: inputHeight,
              },
            ]}
            value={inputText}
            onChangeText={setInputText}
            placeholder="给 AI 教练发消息..."
            placeholderTextColor={isDark ? '#5C5C60' : '#8E8E93'}
            multiline
            maxLength={500}
            editable={!isGenerating}
            scrollEnabled={inputHeight >= inputMaxHeight}
            onSubmitEditing={handleSend}
            onContentSizeChange={handleInputContentSizeChange}
          />
          <TouchableOpacity
            activeOpacity={0.85}
            disabled={isGenerating || !inputText.trim()}
            style={[
              styles.sendButton,
              { backgroundColor: isGenerating || !inputText.trim() ? (isDark ? '#2C2C30' : '#E5E5EA') : '#007AFF' },
            ]}
            onPress={handleSend}
          >
            <Ionicons
              name="arrow-up"
              size={18}
              color={isGenerating || !inputText.trim() ? '#8E8E93' : '#FFFFFF'}
            />
          </TouchableOpacity>
        </View>
      </Animated.View>

      <Modal visible={!!previewAttachment} transparent animationType="fade" onRequestClose={() => setPreviewAttachment(null)}>
        <Pressable style={styles.previewOverlay} onPress={() => setPreviewAttachment(null)}>
          <Pressable style={styles.previewCard} onPress={() => {}}>
            <TouchableOpacity style={styles.previewCloseButton} onPress={() => setPreviewAttachment(null)}>
              <Ionicons name="close" size={18} color="#FFFFFF" />
            </TouchableOpacity>

            {previewAttachment?.kind === 'image' && previewAttachment.uri ? (
              <ExpoImage
                source={{ uri: previewAttachment.uri }}
                style={styles.previewImage}
                contentFit="contain"
              />
            ) : (
              <View style={styles.previewFallback}>
                <Ionicons name="videocam-outline" size={28} color="#FFFFFF" />
                <Text style={styles.previewFallbackText}>当前仅支持图片放大预览</Text>
              </View>
            )}
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={isSessionModalVisible} transparent animationType="fade" onRequestClose={() => setIsSessionModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View
            style={[
              styles.sessionModal,
              {
                backgroundColor: isDark ? '#141418' : '#FFFFFF',
                borderColor: borderCol,
              },
            ]}
          >
            <View style={[styles.sessionModalHeader, { borderBottomColor: borderCol }]}>
              <View>
                <Text style={[styles.sessionModalTitle, { color: textCol }]}>对话列表</Text>
                <Text style={[styles.sessionModalSubtitle, { color: subTextCol }]}>
                  不同主题可以分开聊，长期记忆仍然共享
                </Text>
                <Text style={[styles.sessionModalCount, { color: subTextCol }]}>
                  共 {visibleSessionList.length} 个对话
                </Text>
              </View>
              <TouchableOpacity style={[styles.closeButton, { backgroundColor: isDark ? '#202028' : '#F3F4F6' }]} onPress={() => setIsSessionModalVisible(false)}>
                <Ionicons name="close" size={18} color={textCol} />
              </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.createSessionButton} onPress={handleCreateSession}>
              <Ionicons name="add-circle-outline" size={18} color="#007AFF" />
              <Text style={styles.createSessionText}>新建对话</Text>
            </TouchableOpacity>

            <ScrollView style={styles.sessionListScroll} contentContainerStyle={styles.sessionListContent}>
              {isSessionLoading && (
                <View style={styles.sessionLoading}>
                  <ActivityIndicator size="small" color="#007AFF" />
                </View>
              )}
              {visibleSessionList.length === 0 ? (
                <View style={styles.emptySessionState}>
                  <Text style={[styles.emptySessionTitle, { color: textCol }]}>还没有可显示的对话</Text>
                  <Text style={[styles.emptySessionSubtitle, { color: subTextCol }]}>
                    先新建一个对话，或者稍等片刻让最近会话同步完成。                  </Text>
                </View>
              ) : (
                visibleSessionList.map((session) => {
                  const active = session.id === sessionId;
                  return (
                    <TouchableOpacity
                      key={session.id}
                      style={[
                        styles.sessionItem,
                        {
                          borderColor: active ? '#007AFF' : borderCol,
                          backgroundColor: active
                            ? isDark
                              ? 'rgba(0,122,255,0.12)'
                              : 'rgba(0,122,255,0.06)'
                            : 'transparent',
                        },
                      ]}
                      onPress={() => handleSelectSession(session.id)}
                      onLongPress={() => setMenuSession(session)}
                      delayLongPress={220}
                    >
                      <View style={styles.sessionItemMain}>
                        <View style={styles.sessionTitleRow}>
                          <Text style={[styles.sessionItemTitle, { color: textCol }]} numberOfLines={1}>
                            {session.title || '新的对话'}
                          </Text>
                          {session.is_pinned && <Ionicons name="bookmark" size={12} color="#007AFF" />}
                        </View>
                        <Text style={[styles.sessionItemMeta, { color: subTextCol }]} numberOfLines={1}>
                          {session.last_message_at || session.updated_at || session.created_at || ''}
                        </Text>
                      </View>
                      {active && <Ionicons name="checkmark-circle" size={18} color="#007AFF" />}
                    </TouchableOpacity>
                  );
                })
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      <Modal visible={!!menuSession} transparent animationType="fade" onRequestClose={() => setMenuSession(null)}>
        <Pressable style={styles.menuOverlay} onPress={() => setMenuSession(null)}>
          <View
            style={[
              styles.sessionActionMenu,
              {
                backgroundColor: isDark ? '#1C1C22' : '#FFFFFF',
                borderColor: borderCol,
              },
            ]}
          >
            <Text style={[styles.sessionActionTitle, { color: textCol }]} numberOfLines={1}>
              {menuSession?.title || '新的对话'}
            </Text>
            <TouchableOpacity style={styles.sessionActionItem} onPress={handleTogglePinSession}>
              <Ionicons
                name={menuSession?.is_pinned ? 'bookmark-outline' : 'bookmark'}
                size={16}
                color="#007AFF"
              />
              <Text style={[styles.sessionActionText, { color: textCol }]}>
                {menuSession?.is_pinned ? '取消置顶' : '置顶'}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.sessionActionItem} onPress={handleDeleteSession}>
              <Ionicons name="trash-outline" size={16} color="#FF453A" />
              <Text style={[styles.sessionActionText, { color: '#FF453A' }]}>删除</Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
    paddingHorizontal: 16,
  },
  headerRow: {
    width: '100%',
    maxWidth: 800,
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerLeft: { flex: 1, paddingRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '800' },
  headerSubtitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  headerSubtitle: { fontSize: 12, fontWeight: '500', flexShrink: 1 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  headerRight: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  headerIconButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 0.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusBanner: {
    width: '100%',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderBottomWidth: 0.5,
  },
  statusInner: {
    width: '100%',
    maxWidth: 800,
    alignSelf: 'center',
    flexDirection: 'row',
    alignItems: 'center',
  },
  spinner: { marginRight: 10 },
  statusMessage: { flex: 1, fontSize: 12 },
  chatScroll: { flex: 1 },
  chatContent: {
    alignItems: 'center',
    paddingTop: 100,
    paddingBottom: 215,
    paddingHorizontal: 16,
  },
  chatMaxWidth: { width: '100%', maxWidth: 760, gap: 18 },
  emptyChatHero: {
    width: '100%',
    borderWidth: 0.5,
    borderRadius: 28,
    padding: 22,
    gap: 14,
    marginBottom: 10,
  },
  emptyChatEyebrow: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  emptyChatTitle: {
    fontSize: 26,
    fontWeight: '800',
    lineHeight: 34,
  },
  emptyChatDescription: {
    fontSize: 14,
    lineHeight: 22,
  },
  emptyChatSuggestionList: {
    gap: 10,
    marginTop: 6,
  },
  emptyChatSuggestion: {
    borderWidth: 0.5,
    borderRadius: 18,
    paddingHorizontal: 16,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
  },
  emptyChatSuggestionText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
  },
  messageRow: { width: '100%', flexDirection: 'row', marginVertical: 4 },
  botRow: { justifyContent: 'flex-start', paddingRight: 40 },
  userRow: { justifyContent: 'flex-end', paddingLeft: 40 },
  bubble: {
    maxWidth: '100%',
    borderRadius: 22,
    paddingVertical: 14,
    paddingHorizontal: 18,
  },
  botBubble: { borderWidth: 0.5 },
  userBubble: {
    backgroundColor: '#007AFF',
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.14,
    shadowRadius: 10,
    elevation: 2,
  },
  messageText: { flexShrink: 1 },
  messageParagraph: { marginTop: 10 },
  messageParagraphText: { marginTop: 10 },
  messageBold: { fontWeight: '800' },
  messageAttachment: {
    width: 52,
    height: 52,
    borderRadius: 14,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  messageAttachmentThumb: { width: '100%', height: '100%' },
  messageAttachmentIcon: {
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardContainer: { marginTop: 12, width: '100%' },
  processingLine: { minWidth: 220, flexDirection: 'row', alignItems: 'center' },
  processingText: { flex: 1, fontSize: 13, fontWeight: '600' },
  floatingControls: {
    position: 'absolute',
    left: 0,
    right: 0,
    zIndex: 20,
    alignSelf: 'center',
    width: '100%',
    maxWidth: 780,
    paddingHorizontal: 16,
    paddingTop: 6,
    gap: 8,
  },
  pendingAttachmentBar: {
    width: '100%',
    borderRadius: 18,
    borderWidth: 0.5,
    paddingHorizontal: 12,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  pendingAttachmentMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  pendingAttachmentThumb: { width: 36, height: 36, borderRadius: 10 },
  pendingAttachmentIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
  },
  pendingAttachmentTextWrap: { flex: 1 },
  pendingAttachmentTitle: { fontSize: 13, fontWeight: '700' },
  pendingAttachmentSubtitle: { fontSize: 11, marginTop: 2 },
  pendingAttachmentClose: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  controlBar: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
  },
  modeCapsule: {
    width: 92,
    height: 28,
    borderRadius: 14,
    borderWidth: 0.5,
    flexDirection: 'row',
    padding: 2,
    position: 'relative',
    overflow: 'hidden',
  },
  capsuleSlider: {
    position: 'absolute',
    top: 2,
    width: 44,
    height: 24,
    borderRadius: 12,
    backgroundColor: '#007AFF',
  },
  capsuleOption: { flex: 1, alignItems: 'center', justifyContent: 'center', zIndex: 1 },
  capsuleText: { fontSize: 11, fontWeight: '600' },
  sheetButtonShell: {
    height: 28,
    borderRadius: 14,
    borderWidth: 0.5,
    overflow: 'hidden',
  },
  sheetButtonInner: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sheetButtonText: { fontSize: 11, fontWeight: '600' },
  floatingInput: {
    width: '100%',
    borderRadius: 28,
    borderWidth: 0.5,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: -3 },
    shadowOpacity: 0.18,
    shadowRadius: 15,
    elevation: 6,
  },
  attachButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  textInput: {
    flex: 1,
    minHeight: 42,
    paddingVertical: 8,
    marginRight: 12,
    overflow: 'hidden',
    textAlignVertical: 'top',
    ...Platform.select({ web: { outlineStyle: 'none' } }),
  } as any,
  sendButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  sessionModal: {
    width: '100%',
    maxWidth: 420,
    height: '76%',
    borderRadius: 22,
    borderWidth: 0.5,
    overflow: 'hidden',
  },
  sessionModalHeader: {
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 0.5,
  },
  sessionModalTitle: { fontSize: 18, fontWeight: '800' },
  sessionModalSubtitle: { fontSize: 12, marginTop: 4 },
  sessionModalCount: { fontSize: 11, marginTop: 4 },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  createSessionButton: {
    paddingHorizontal: 18,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  createSessionText: { color: '#007AFF', fontSize: 14, fontWeight: '700' },
  sessionListScroll: { flex: 1 },
  sessionListContent: { paddingHorizontal: 16, paddingBottom: 16, gap: 10 },
  sessionLoading: { paddingVertical: 24, alignItems: 'center' },
  emptySessionState: { paddingVertical: 24, alignItems: 'center', gap: 8 },
  emptySessionTitle: { fontSize: 14, fontWeight: '700' },
  emptySessionSubtitle: { fontSize: 12, textAlign: 'center', lineHeight: 18 },
  sessionItem: {
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  sessionItemMain: { flex: 1 },
  sessionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sessionItemTitle: { fontSize: 14, fontWeight: '700' },
  sessionItemMeta: { fontSize: 11, marginTop: 4 },
  menuOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.18)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  previewOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.82)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  previewCard: {
    width: '100%',
    maxWidth: 520,
    maxHeight: '82%',
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: '#111216',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
  },
  previewCloseButton: {
    position: 'absolute',
    top: 12,
    right: 12,
    zIndex: 2,
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  previewImage: { width: '100%', height: 420, borderRadius: 18 },
  previewFallback: { alignItems: 'center', justifyContent: 'center', paddingVertical: 56, gap: 10 },
  previewFallbackText: { color: '#FFFFFF', fontSize: 13, fontWeight: '600' },
  sessionActionMenu: {
    width: '100%',
    maxWidth: 280,
    borderRadius: 18,
    borderWidth: 0.5,
    padding: 10,
  },
  sessionActionTitle: { fontSize: 14, fontWeight: '700', marginBottom: 8, paddingHorizontal: 8, paddingTop: 6 },
  sessionActionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 10,
    paddingVertical: 12,
    borderRadius: 12,
  },
  sessionActionText: { fontSize: 14, fontWeight: '600' },
});
