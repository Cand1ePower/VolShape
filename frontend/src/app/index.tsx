import React, { useState, useCallback, useEffect, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  KeyboardAvoidingView, 
  Platform, 
  useColorScheme, 
  ActivityIndicator,
  useWindowDimensions,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Modal
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { connectChatStream } from '../services/sse';
import { WorkoutCard } from '../components/ui/WorkoutCard';
import { DietCard } from '../components/ui/DietCard';
import { useAuth } from '../contexts/AuthContext';
import { usePlan } from '../contexts/PlanContext';

// 自定义商业级 Message 强类型结构
interface Message {
  id: string;
  text: string;
  isBot: boolean;
  createdAt: Date;
  customCard?: any;
}

// 自动检测不同平台下的本地服务 IP 地址
const getBackendUrl = () => {
  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:8000/api/chat/stream';
  }
  return 'http://localhost:8000/api/chat/stream';
};

export default function ChatScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  
  // 响应式极速尺寸计算 (Responsive Dimensions Engine)
  const isSmallScreen = width < 375;
  const isLargeScreen = width > 768;
  const maxWrapperWidth = 800; // 与大厂 ChatGPT/Claude 看齐的最大内容宽度
  
  const dynamicFontSize = isSmallScreen ? 14 : 15;

  // Auth
  const { token, userId, sessionId, isLoggedIn } = useAuth();
  const { resetPlan } = usePlan();

  // Clear training plan on logout
  useEffect(() => {
    if (!isLoggedIn) resetPlan();
  }, [isLoggedIn]);

  // Chat mode
  const [mode, setMode] = useState<'quick' | 'detailed'>('quick');

  // 聊天消息列表状态
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [agentStatus, setAgentStatus] = useState<{ node: string; message: string } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // 引用引用
  const currentBotTextRef = useRef('');
  const esRef = useRef<any>(null);
  const scrollViewRef = useRef<ScrollView>(null);

  // 组件卸载时安全关闭 EventSource
  useEffect(() => {
    return () => {
      if (esRef.current) {
        esRef.current.close();
      }
    };
  }, []);

  // 自动滚动到底部
  const scrollToBottom = (animated = true) => {
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated });
    }, 100);
  };

  // Load history on login, clear on logout
  useEffect(() => {
    if (!isLoggedIn || !sessionId) {
      setMessages([]);
      return;
    }
    (async () => {
      try {
        const baseUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
        const resp = await fetch(`${baseUrl}/api/chat/history?session_id=${sessionId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await resp.json();
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages.map((m: any, i: number) => ({
            id: `hist-${i}`,
            text: m.content,
            isBot: m.role === 'assistant',
            createdAt: new Date(),
          })));
        } else {
          setMessages([{
            id: 'welcome', text: '你好！我是 VolShape AI 教练。告诉我你的健身目标或今天的训练需求吧。',
            isBot: true, createdAt: new Date(),
          }]);
        }
      } catch {
        setMessages([{
          id: 'welcome', text: '你好！我是 VolShape AI 教练。后端未连接，请先启动服务。',
          isBot: true, createdAt: new Date(),
        }]);
      }
    })();
  }, [isLoggedIn, sessionId]);

  // 发送消息与流式处理逻辑
  const handleSend = useCallback(() => {
    if (isGenerating || !inputText.trim()) return;

    const userText = inputText.trim();
    setInputText('');

    const userMsg: Message = {
      id: Math.random().toString(36).substring(7),
      text: userText,
      isBot: false,
      createdAt: new Date()
    };

    // 1. 追加用户消息
    setMessages((prev) => [...prev, userMsg]);
    setIsGenerating(true);
    setAgentStatus({ node: 'Intent Classifier', message: '分析用户输入意图并静默同步记忆...' });
    scrollToBottom(true);

    // 2. 创建机器人的空消息以备流式追加
    const botMessageId = Math.random().toString(36).substring(7);
    const initialBotMessage: Message = {
      id: botMessageId,
      text: '',
      isBot: true,
      createdAt: new Date(),
    };

    setMessages((prev) => [...prev, initialBotMessage]);

    currentBotTextRef.current = '';

    // 3. 建立 SSE 连接
    const url = getBackendUrl();
    if (!token) return;
    // Use auth context token
    
    esRef.current = connectChatStream(
      url,
      token,
      {
        user_input: userText,
        session_id: sessionId || 'default',
        mode: mode,
      },
      {
        onOpen: () => {
          console.log('SSE connection opened successfully');
        },
        onState: (state) => {
          setAgentStatus(state);
          scrollToBottom(true);
        },
        onToken: (tokenText) => {
          currentBotTextRef.current += tokenText;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === botMessageId
                ? { ...msg, text: currentBotTextRef.current }
                : msg
            )
          );
          scrollToBottom(false); // 打字机追加时平滑滚动
        },
        onUI: (cardData) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === botMessageId
                ? { ...msg, customCard: cardData }
                : msg
            )
          );
          scrollToBottom(true);
        },
        onDone: () => {
          setIsGenerating(false);
          setAgentStatus(null);
          scrollToBottom(true);
          console.log('SSE stream finished.');
        },
        onError: (err) => {
          setIsGenerating(false);
          setAgentStatus(null);
          console.error('SSE Error:', err);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === botMessageId
                ? { ...msg, text: '⚠️ 智能体图执行异常。这可能是因为网络连接问题，或没有执行 PostgreSQL Fallback 降级。请确保后端已经正常启动！' }
                : msg
            )
          );
          scrollToBottom(true);
        },
      }
    );
  }, [inputText, isGenerating, token, mode, sessionId]);

  // 主题配色
  const bgCol = isDark ? '#0A0A0C' : '#F5F5F7';
  const headerBg = isDark ? 'rgba(18, 18, 22, 0.85)' : 'rgba(255, 255, 255, 0.85)';
  const borderCol = isDark ? '#1F1F24' : '#E5E5EA';
  const textCol = isDark ? '#FFFFFF' : '#1C1C1E';
  const subTextCol = isDark ? '#8E8E93' : '#666666';
  const inputBg = isDark ? '#1C1C21' : '#FFFFFF';

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: bgCol }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: headerBg, borderBottomColor: borderCol, paddingTop: Math.max(insets.top, 16) + (Platform.OS === 'web' ? 72 : 0) }]}>
        <View style={styles.headerRow}>
          <View style={styles.statusDotWrap}>
            <View style={[styles.statusDot, { backgroundColor: isGenerating ? '#34C759' : isLoggedIn ? '#007AFF' : '#AEAEB2' }]} />
            <Text style={[styles.headerSubtitle, { color: subTextCol }]}>
              {isGenerating ? '思考中...' : isLoggedIn ? '在线' : '未登录'}
            </Text>
          </View>
        </View>
      </View>

      {/* 智能体执行状态显示区（LangGraph 节点流） */}
      {agentStatus && (
        <View style={[styles.statusBanner, { backgroundColor: isDark ? 'rgba(0, 122, 255, 0.08)' : 'rgba(0, 122, 255, 0.04)', borderBottomColor: borderCol }]}>
          <View style={styles.statusLimit}>
            <ActivityIndicator size="small" color="#007AFF" style={styles.spinner} />
            <View style={styles.statusTextContainer}>
              <Text style={[styles.statusNode, { color: '#007AFF' }]}>[{agentStatus.node}]</Text>
              <Text style={[styles.statusMessage, { color: isDark ? '#AEAEB2' : '#666666' }]} numberOfLines={1}>
                {agentStatus.message}
              </Text>
            </View>
          </View>
        </View>
      )}

      {/* 核心大厂级高度响应式消息流区域 */}
      <KeyboardAvoidingView 
        style={styles.keyboardContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          ref={scrollViewRef}
          style={styles.chatScroll}
          contentContainerStyle={styles.chatContent}
          onContentSizeChange={() => scrollToBottom(true)}
        >
          <View style={styles.maxWidthContainer}>
            {messages.map((msg) => (
              <View 
                key={msg.id} 
                style={[
                  styles.messageRow, 
                  msg.isBot ? styles.botRow : styles.userRow
                ]}
              >
                {/* 消息气泡 - 🛡️【商业化重构】在 Web 上 100% 完美的自动折行计算 */}
                <View 
                  style={[
                    styles.bubble, 
                    msg.isBot 
                      ? [styles.botBubble, { backgroundColor: isDark ? '#1C1C21' : '#E9E9EB', borderColor: borderCol }] 
                      : [styles.userBubble, { backgroundColor: '#007AFF' }]
                  ]}
                >
                  {msg.text ? (
                    <Text 
                      style={[
                        styles.messageText, 
                        { 
                          fontSize: dynamicFontSize, 
                          color: msg.isBot ? textCol : '#FFFFFF',
                          lineHeight: dynamicFontSize + 6
                        }
                      ]}
                    >
                      {msg.text}
                    </Text>
                  ) : isGenerating && msg.isBot ? (
                    <ActivityIndicator size="small" color="#007AFF" />
                  ) : null}

                  {/* Generative UI 卡片渲染入口 */}
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
            ))}
          </View>
        </ScrollView>

        {/* Input Area */}
        <View style={styles.inputArea}>
          {/* Mode Toggle */}
          <View style={styles.modeToggle}>
            <TouchableOpacity activeOpacity={0.7} style={[styles.modeChip, mode === 'quick' && styles.modeChipActive]} onPress={() => setMode('quick')}>
              <Text style={[styles.modeChipText, mode === 'quick' && styles.modeChipTextActive]}>⚡ 快速</Text>
            </TouchableOpacity>
            <TouchableOpacity activeOpacity={0.7} style={[styles.modeChip, mode === 'detailed' && styles.modeChipActive]} onPress={() => setMode('detailed')}>
              <Text style={[styles.modeChipText, mode === 'detailed' && styles.modeChipTextActive]}>🔍 详细</Text>
            </TouchableOpacity>
          </View>

          <View style={[styles.inputWrapper, { backgroundColor: inputBg, borderColor: borderCol }]}>
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
              activeOpacity={0.8}
              disabled={isGenerating || !inputText.trim()}
              style={[styles.sendBtn, { backgroundColor: (isGenerating || !inputText.trim()) ? (isDark ? '#2C2C30' : '#E5E5EA') : '#007AFF' }]}
              onPress={handleSend}
            >
              <Text style={[styles.sendBtnText, { color: (isGenerating || !inputText.trim()) ? '#8E8E93' : '#FFFFFF' }]}>↑</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  // ── Header ──
  header: {
    borderBottomWidth: 0.5,
    paddingHorizontal: 20,
    paddingVertical: 14,
    width: '100%',
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    maxWidth: 800,
    alignSelf: 'center',
  },
  headerLeft: { gap: 2 },
  headerTitle: { fontSize: 20, fontWeight: '800', letterSpacing: -0.8 },
  headerSubtitleContainer: { flexDirection: 'row', alignItems: 'center', marginTop: 3, gap: 6 },
  statusDotWrap: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  headerSubtitle: { fontSize: 12, fontWeight: '500' },
  headerRight: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  headerBtn: {
    paddingVertical: 8, paddingHorizontal: 14, borderRadius: 10,
    borderWidth: 1, borderColor: 'transparent',
  },
  headerBtnPrimary: { backgroundColor: '#007AFF', borderColor: '#007AFF' },
  headerBtnDanger: { backgroundColor: 'rgba(255,59,48,0.1)', borderColor: 'rgba(255,59,48,0.25)' },
  headerBtnText: { fontSize: 13, fontWeight: '600', color: '#007AFF' },
  // ── Status Banner ──
  statusBanner: {
    paddingVertical: 10, paddingHorizontal: 20, alignItems: 'center',
    borderBottomWidth: 0.5, width: '100%',
  },
  statusLimit: { flexDirection: 'row', alignItems: 'center', width: '100%', maxWidth: 800 },
  spinner: { marginRight: 10 },
  statusTextContainer: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusNode: { fontSize: 12, fontWeight: '700' },
  statusMessage: { fontSize: 12, flex: 1 },
  // ── Chat ──
  keyboardContainer: { flex: 1, width: '100%', alignItems: 'center' },
  chatScroll: { flex: 1, width: '100%' },
  chatContent: { alignItems: 'center', paddingVertical: 24, paddingHorizontal: 20, width: '100%' },
  maxWidthContainer: { width: '100%', maxWidth: 760, gap: 20 },
  messageRow: { width: '100%', flexDirection: 'row', marginVertical: 4 },
  botRow: { justifyContent: 'flex-start', paddingRight: 40 },
  userRow: { justifyContent: 'flex-end', paddingLeft: 40 },
  bubble: {
    borderRadius: 22, paddingVertical: 14, paddingHorizontal: 18,
    maxWidth: '100%', flexDirection: 'column',
  },
  botBubble: { borderWidth: 0.5, alignSelf: 'flex-start' },
  userBubble: {
    alignSelf: 'flex-end',
    shadowColor: '#007AFF', shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2, shadowRadius: 8, elevation: 3,
  },
  messageText: { flexShrink: 1, lineHeight: 22, fontSize: 15 },
  cardContainer: { marginTop: 12, width: '100%' },
  // ── Input ──
  inputArea: {
    width: '100%', maxWidth: 780,
    paddingHorizontal: 20, paddingBottom: Platform.OS === 'ios' ? 12 : 20,
    paddingTop: 8, alignItems: 'center',
  },
  modeToggle: { flexDirection: 'row', gap: 8, marginBottom: 10, alignSelf: 'center' },
  modeChip: { paddingVertical: 5, paddingHorizontal: 14, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(0,122,255,0.2)' },
  modeChipActive: { backgroundColor: 'rgba(0,122,255,0.12)', borderColor: '#007AFF' },
  modeChipText: { fontSize: 12, fontWeight: '600', color: '#8E8E93' },
  modeChipTextActive: { color: '#007AFF' },
  inputWrapper: {
    width: '100%', borderRadius: 28, borderWidth: 1,
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 18, paddingVertical: 8,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04, shadowRadius: 12, elevation: 1,
  },
  textInput: {
    flex: 1, maxHeight: 120, paddingVertical: 8, marginRight: 12, fontSize: 15,
    ...Platform.select({ web: { outlineStyle: 'none' } }),
  } as any,
  sendBtn: {
    width: 36, height: 36, borderRadius: 18,
    justifyContent: 'center', alignItems: 'center',
  },
  sendBtnText: { fontSize: 18, fontWeight: '700' },
  // ── Login Modal ──
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center', alignItems: 'center', padding: 24,
  },
  loginModal: {
    width: '100%', maxWidth: 380, borderRadius: 24,
    borderWidth: 0.5, padding: 28,
  },
  loginTitle: { fontSize: 22, fontWeight: '800', textAlign: 'center', marginBottom: 6, letterSpacing: -0.5 },
  loginSub: { fontSize: 13, textAlign: 'center', marginBottom: 24, lineHeight: 18 },
  presetAccounts: { gap: 10, marginBottom: 20 },
  presetBtn: { padding: 16, borderRadius: 16, gap: 4 },
  presetBtnLabel: { fontSize: 15, fontWeight: '700' },
  presetBtnId: { fontSize: 11, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }) },
  loginDivider: { textAlign: 'center', fontSize: 12, marginBottom: 20 },
  loginInput: {
    borderWidth: 1, borderRadius: 14, padding: 14, fontSize: 14,
    marginBottom: 16, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }),
  },
  loginConfirmBtn: { borderRadius: 16, paddingVertical: 16, alignItems: 'center', marginBottom: 12 },
  loginConfirmText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
  loginCancelBtn: { alignItems: 'center', paddingVertical: 8 },
  // ── Memory Modal ──
  modalContent: {
    width: '100%', maxWidth: 680, height: '82%',
    borderRadius: 24, borderWidth: 0.5, overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 20, borderBottomWidth: 0.5, borderBottomColor: '#2C2C2E',
  },
  modalTitle: { fontSize: 18, fontWeight: '800', letterSpacing: -0.5 },
  modalSubtitle: { fontSize: 11, marginTop: 4 },
  closeBtn: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center' },
  closeBtnText: { fontSize: 14, fontWeight: '700' },
  modalLoading: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 16 },
  loadingText: { fontSize: 13, fontWeight: '600' },
  modalScroll: { flex: 1 },
  jsonConsoleBg: { padding: 16 },
  consoleSection: { borderWidth: 0.5, borderRadius: 14, padding: 16, marginBottom: 2 },
  consoleSectionTitle: { fontSize: 11, fontWeight: '800', color: '#007AFF', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.8 },
  consoleMetaRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5 },
  consoleKey: { fontSize: 12, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }) },
  consoleValString: { fontSize: 12, fontWeight: '700' },
  consoleValArray: { fontSize: 12, fontWeight: '700' },
  consoleValNum: { fontSize: 12, fontWeight: '700' },
  rawJsonSection: { borderWidth: 0.5, borderRadius: 14, padding: 16, marginTop: 14 },
  rawJsonText: { fontSize: 10, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }), lineHeight: 15 },
  modalFooter: { padding: 16, borderTopWidth: 0.5, alignItems: 'center' },
  refreshBtn: { width: '100%', borderRadius: 14, paddingVertical: 14, alignItems: 'center' },
  refreshBtnText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
  eventRow: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 8,
    borderBottomWidth: 0.5, gap: 8,
  },
  eventTypeBadge: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
    minWidth: 52, alignItems: 'center',
  },
  eventTypeText: { fontSize: 10, fontWeight: '800' },
  eventDate: { fontSize: 10, width: 72 },
  eventPayload: { fontSize: 10, flex: 1 },
});
