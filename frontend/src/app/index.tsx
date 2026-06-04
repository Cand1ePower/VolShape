import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
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
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from 'expo-router';

import { WorkoutCard } from '../components/ui/WorkoutCard';
import { DietCard } from '../components/ui/DietCard';
import { useAuth } from '../contexts/AuthContext';
import { usePlan } from '../contexts/PlanContext';
import { connectChatStream } from '../services/sse';
import { getBackendBaseUrl } from '@/services/api';

interface Message {
  id: string;
  text: string;
  isBot: boolean;
  createdAt: Date;
  customCard?: any;
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

const getBackendUrl = () => `${getBackendBaseUrl()}/api/chat/stream`;

const WELCOME_TEXT = '你好，我是 VolShape AI 教练。告诉我你的训练目标、今天的需求，或者直接让我开始制定计划。';
const LOGIN_WELCOME_TEXT = '你好，我是 VolShape AI 教练。请先登录后再继续使用。';
const HISTORY_ERROR_TEXT = '你好，我是 VolShape AI 教练。当前聊天记录加载失败，请稍后重试。';

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

  const floatingBaseBottom = Platform.OS === 'ios' ? 80 : 62;
  const keyboardGap = Platform.OS === 'ios' ? 8 : 42;

  const bgCol = isDark ? '#0A0A0C' : '#F5F5F7';
  const borderCol = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';
  const textCol = isDark ? '#FFFFFF' : '#111827';
  const subTextCol = isDark ? '#A1A1AA' : '#6B7280';
  const botBubbleBg = isDark ? 'rgba(24, 24, 28, 0.78)' : 'rgba(255, 255, 255, 0.9)';
  const frostedBg = isDark ? 'rgba(18, 18, 22, 0.9)' : 'rgba(255, 255, 255, 0.92)';
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
    if (isGenerating || !inputText.trim()) return;
    if (!sessionId) {
      await refreshSessions();
      return;
    }

    const userText = inputText.trim();
    setInputText('');
    setMessages((prev) => [
      ...prev,
      { id: Math.random().toString(36).slice(2), text: userText, isBot: false, createdAt: new Date() },
    ]);
    setIsGenerating(true);
    const initialStatus = { node: 'Intent Classifier', message: '正在分析用户意图...' };
    setAgentStatus(initialStatus);
    setProcessingMessage(formatProcessingMessage(initialStatus));
    scrollToBottom(true);

    const botMessageId = Math.random().toString(36).slice(2);
    setMessages((prev) => [...prev, { id: botMessageId, text: '', isBot: true, createdAt: new Date() }]);
    currentBotTextRef.current = '';

    const validToken = await getValidToken();
    if (!validToken) {
      setIsGenerating(false);
      setAgentStatus(null);
      setMessages((prev) =>
        prev.map((msg) => (msg.id === botMessageId ? { ...msg, text: '请先登录后再继续使用 AI 教练。' } : msg))
      );
      return;
    }

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
          currentBotTextRef.current += tokenText;
          setMessages((prev) =>
            prev.map((msg) => (msg.id === botMessageId ? { ...msg, text: currentBotTextRef.current } : msg))
          );
          scrollToBottom(false);
        },
        onUI: (cardData) => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === botMessageId ? { ...msg, customCard: cardData } : msg))
          );
          scrollToBottom(true);
        },
        onDone: () => {
          setIsGenerating(false);
          setAgentStatus(null);
          refreshSessions();
          scrollToBottom(true);
        },
        onError: (err) => {
          setIsGenerating(false);
          setAgentStatus(null);
          esRef.current?.close?.();
          const message = err?.message || '系统处理本次消息时发生异常，本次结果已停止生成。';
          const suffix = err?.code ? `\n\n错误码：${err.code}` : '';
          setMessages((prev) =>
            prev.map((msg) => (msg.id === botMessageId ? { ...msg, text: `⚠️ ${message}${suffix}` } : msg))
          );
          scrollToBottom(true);
        },
      }
    );
  }, [
    formatProcessingMessage,
    getValidToken,
    inputText,
    isGenerating,
    mode,
    refreshSessions,
    scrollToBottom,
    sessionId,
    useTrainingSheet,
  ]);

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
          data.messages.map((message: any, index: number) => ({
            id: `hist-${message.created_at || index}`,
            text: message.content,
            isBot: message.role === 'assistant',
            createdAt: message.created_at ? new Date(message.created_at) : new Date(),
            customCard: message.customCard || undefined,
          }))
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
                  {msg.text ? (
                    <Text
                      selectable
                      style={[
                        styles.messageText,
                        {
                          color: msg.isBot ? textCol : '#FFFFFF',
                          fontSize: dynamicFontSize,
                          lineHeight: dynamicFontSize + 7,
                        },
                      ]}
                    >
                      {msg.text}
                    </Text>
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
                        <DietCard data={msg.customCard} />
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
                  训练表
                </Animated.Text>
              </TouchableOpacity>
            </Animated.View>
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
          <TextInput
            style={[styles.textInput, { color: textCol, fontSize: dynamicFontSize }]}
            value={inputText}
            onChangeText={setInputText}
            placeholder="给 AI 教练发消息..."
            placeholderTextColor={isDark ? '#5C5C60' : '#8E8E93'}
            multiline
            maxLength={500}
            editable={!isGenerating}
            onSubmitEditing={handleSend}
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
                    先新建一个对话，或者稍等片刻让最近会话同步完成。
                  </Text>
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
  textInput: {
    flex: 1,
    maxHeight: 120,
    paddingVertical: 8,
    marginRight: 12,
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
