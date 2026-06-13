import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from 'react-native';

import { useThemeController } from '@/contexts/ThemeContext';
import { fetchPublicHealth, runPublicRagTest } from '@/services/public';

const APK_DOWNLOAD_URL =
  process.env.EXPO_PUBLIC_APP_DOWNLOAD_URL?.trim() ||
  'https://expo.dev/artifacts/eas/aXaYpUHmZtv2RJ22Nps34F0s8DmTCzdMyBuZ0tOxr1w.apk';

const FEATURE_CARDS = [
  {
    title: '训练',
    bodyTitle: '把计划生成、执行反馈、动态修正放进同一条对话里',
    body: '不需要反复切换表单，用户只要描述目标，系统就能持续更新建议。',
    icon: 'bar-chart-outline',
  },
  {
    title: '饮食',
    bodyTitle: '用拍照和对话代替手动录卡路里',
    body: '识别食物、计算热量，再把结果写回到用户长期画像和后续建议里。',
    icon: 'camera-outline',
  },
  {
    title: '记忆',
    bodyTitle: '记住用户的身体状态、偏好变化和长期约束',
    body: '让 AI 教练不是一次性回答器，而是能随状态变化的长期陪伴系统。',
    icon: 'git-network-outline',
  },
];

function formatSourceMeta(source: { page_start?: number | null; page_end?: number | null; heading_path: string[] }) {
  const heading = source.heading_path?.slice(-2).join(' / ');
  let page = '';
  if (source.page_start) {
    page = `P.${source.page_start}`;
    if (source.page_end && source.page_end !== source.page_start) {
      page = `P.${source.page_start}-${source.page_end}`;
    }
  }

  if (heading && page) return `${heading} · ${page}`;
  return heading || page || '知识库片段';
}

async function openExternal(url: string) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.open(url, '_blank', 'noopener,noreferrer');
    return;
  }
  await Linking.openURL(url);
}

function HeaderButton({
  label,
  icon,
  onPress,
  textColor,
}: {
  label?: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  textColor: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ hovered, pressed }) => [
        styles.glassButton,
        {
          opacity: pressed ? 0.92 : 1,
          backgroundColor: hovered ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)',
          borderColor: hovered ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)',
        },
      ]}
    >
      <Ionicons name={icon} size={label ? 16 : 18} color="#8E8E93" />
      {label ? <Text style={[styles.headerButtonText, { color: textColor }]}>{label}</Text> : null}
    </Pressable>
  );
}

export default function WebEntryPage() {
  const { width } = useWindowDimensions();
  const { isDark, toggleTheme } = useThemeController();
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthResult, setHealthResult] = useState('');
  const [ragQuery, setRagQuery] = useState('DOMS 延迟性肌肉酸痛到底是什么，应该怎么恢复？');
  const [ragLoading, setRagLoading] = useState(false);
  const [ragError, setRagError] = useState('');
  const [ragResult, setRagResult] = useState<Awaited<ReturnType<typeof runPublicRagTest>> | null>(null);

  const isMobile = width < 768;
  const textPrimary = isDark ? '#E5E1E4' : '#E5E1E4';
  const textSecondary = '#8E8E93';
  const textMuted = '#585961';

  const handleHealthCheck = async () => {
    setHealthLoading(true);
    try {
      const payload = await fetchPublicHealth();
      const checks = Object.entries(payload.checks || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join(' · ');
      setHealthResult(`${payload.status}${checks ? ` · ${checks}` : ''}`);
    } catch (error: any) {
      setHealthResult(error?.message || '服务检查失败');
    } finally {
      setHealthLoading(false);
    }
  };

  const handleRagTest = async () => {
    const trimmed = ragQuery.trim();
    if (!trimmed || ragLoading) return;

    setRagLoading(true);
    setRagError('');
    try {
      const payload = await runPublicRagTest(trimmed);
      setRagResult(payload);
    } catch (error: any) {
      setRagResult(null);
      const retryAfter = Number(error?.retryAfter || 0);
      if (retryAfter > 0) {
        const minutes = Math.ceil(retryAfter / 60);
        setRagError(`公开体验请求过于频繁，请约 ${minutes} 分钟后再试。`);
      } else {
        setRagError(error?.message || '知识库测试失败');
      }
    } finally {
      setRagLoading(false);
    }
  };

  return (
    <ScrollView
      style={styles.page}
      contentContainerStyle={styles.pageScrollContent}
      showsVerticalScrollIndicator={false}
    >
      <View pointerEvents="none" style={styles.backgroundWaves}>
        <View style={styles.ambientBandOne} />
        <View style={styles.ambientBandTwo} />
        <View style={styles.wavePrimary} />
        <View style={styles.waveSecondary} />
        <View style={styles.waveAccentOne} />
        <View style={styles.waveAccentTwo} />
        <View style={styles.overlayFade} />
      </View>

      <View style={styles.pageShell}>
        <View style={[styles.header, isMobile ? styles.headerMobile : null]}>
          <View style={styles.logoWrap}>
            <View style={styles.logoBadge}>
              <Image source={require('../../assets/images/icon.png')} style={styles.logoImage} contentFit="cover" />
            </View>
            <View>
              <Text style={styles.logoTitle}>VolShape</Text>
              <Text style={styles.logoMeta}>AI-native 健身教练</Text>
            </View>
          </View>

          <View style={styles.headerNav}>
            <HeaderButton
              label={healthLoading ? '检查中' : '服务器健康'}
              icon="pulse-outline"
              onPress={handleHealthCheck}
              textColor={textPrimary}
            />
            <HeaderButton
              label="体验网页版"
              icon="open-outline"
              onPress={() => router.push('/coach')}
              textColor={textPrimary}
            />
            <HeaderButton
              icon={isDark ? 'sunny-outline' : 'moon-outline'}
              onPress={toggleTheme}
              textColor={textPrimary}
            />
          </View>
        </View>

        <View style={styles.main}>
          <View style={styles.heroSection}>
            <View style={styles.heroBadge}>
              <Text style={styles.heroBadgeText}>对话型训练、饮食、记忆闭环</Text>
            </View>

            <Text style={[styles.heroTitle, isMobile ? styles.heroTitleMobile : null]}>
              只通过聊天，完成训练规划、饮食记录。
            </Text>

            <View style={[styles.heroActions, isMobile ? styles.heroActionsMobile : null]}>
              <Pressable
                onPress={() => openExternal(APK_DOWNLOAD_URL)}
                style={({ hovered, pressed }) => [
                  styles.downloadButton,
                  {
                    opacity: pressed ? 0.92 : 1,
                    backgroundColor: hovered ? '#ffffff' : '#cde5ff',
                  },
                ]}
              >
                <Ionicons name="download-outline" size={20} color="#001f2a" />
                <Text style={styles.downloadButtonText}>下载 APP</Text>
              </Pressable>

              <Pressable
                onPress={() => router.push('/coach')}
                style={({ hovered, pressed }) => [
                  styles.glassButton,
                  styles.heroGlassButton,
                  {
                    opacity: pressed ? 0.92 : 1,
                    backgroundColor: hovered ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.03)',
                  },
                ]}
              >
                <Ionicons name="chatbubble-ellipses-outline" size={20} color="#FFFFFF" />
                <Text style={styles.heroGlassButtonText}>体验网页版</Text>
              </Pressable>
            </View>

            {!!healthResult && (
              <View style={styles.healthStatus}>
                <Ionicons name="server-outline" size={16} color="#8ddcff" />
                <Text style={styles.healthStatusText}>{healthResult}</Text>
              </View>
            )}
          </View>

          <View style={[styles.featureGrid, isMobile ? styles.featureGridMobile : null]}>
            {FEATURE_CARDS.map((card) => (
              <View key={card.title} style={styles.featureCard}>
                <View style={styles.featureCardTop}>
                  <Text style={styles.featureCardEyebrow}>{card.title}</Text>
                  <Ionicons name={card.icon as any} size={18} color={textMuted} />
                </View>
                <Text style={styles.featureCardTitle}>{card.bodyTitle}</Text>
                <Text style={styles.featureCardBody}>{card.body}</Text>
              </View>
            ))}
          </View>

          <View style={styles.ragSection}>
            <View style={[styles.ragHeader, isMobile ? styles.ragHeaderMobile : null]}>
              <View style={styles.ragHeaderMain}>
                <Text style={styles.ragTitle}>RAG 知识库测试</Text>
                <Text style={styles.ragDesc}>
                  这里里的项目目前探索模式使用的知识库链路：runtime artifact + Qdrant 向量检索 + BM25 关键词召回 + 本地融合重排。
                </Text>
              </View>
              <Text style={styles.ragLimit}>需 5 分钟最多 10 次</Text>
            </View>

            <View style={[styles.ragComposer, isMobile ? styles.ragComposerMobile : null]}>
              <TextInput
                value={ragQuery}
                onChangeText={setRagQuery}
                placeholder="DOMS 延迟性肌肉酸痛到底是什么，应该怎么恢复？"
                placeholderTextColor={textSecondary}
                style={styles.ragInput}
                multiline={!isMobile}
              />
              <Pressable
                onPress={handleRagTest}
                disabled={ragLoading}
                style={({ hovered, pressed }) => [
                  styles.ragSend,
                  {
                    opacity: ragLoading ? 0.7 : pressed ? 0.92 : 1,
                    backgroundColor: hovered ? 'rgba(141,220,255,0.2)' : 'rgba(141,220,255,0.1)',
                  },
                ]}
              >
                {ragLoading ? (
                  <ActivityIndicator size="small" color="#8ddcff" />
                ) : (
                  <Ionicons name="paper-plane-outline" size={18} color="#8ddcff" />
                )}
              </Pressable>
            </View>

            {!!ragError && (
              <View style={styles.noticeBox}>
                <Ionicons name="alert-circle-outline" size={16} color="#ffb4b4" />
                <Text style={styles.noticeText}>{ragError}</Text>
              </View>
            )}

            {!!ragResult && (
              <View style={styles.resultBlock}>
                <View style={styles.resultTop}>
                  <Text style={styles.resultTitle}>回答摘要</Text>
                  <Text style={styles.resultMeta}>
                    {ragResult.retrieval_mode} · {ragResult.hit_count} hits
                  </Text>
                </View>

                <Text style={styles.resultAnswer}>
                  {ragResult.answer || '本次未生成总结答案，下方展示检索到的证据片段。'}
                </Text>

                {ragResult.llm_degraded ? (
                  <View style={styles.noticeBox}>
                    <Ionicons name="warning-outline" size={16} color="#f9dea6" />
                    <Text style={styles.noticeText}>
                      本次回答降级为检索结果展示。原因：{ragResult.llm_error || 'LLM 不可用'}
                    </Text>
                  </View>
                ) : null}

                {!!ragResult.hits?.length && (
                  <View style={styles.hitList}>
                    {ragResult.hits.map((hit, index) => (
                      <View key={`${hit.title}-${index}`} style={styles.hitCard}>
                        <View style={styles.hitTop}>
                          <Text style={styles.hitTitle}>{hit.title}</Text>
                          <Text style={styles.hitScore}>{hit.score.toFixed(2)}</Text>
                        </View>
                        <Text style={styles.hitMeta}>
                          {formatSourceMeta(hit)} · {hit.source_type} · {hit.score_type}
                        </Text>
                        <Text style={styles.hitPreview}>{hit.preview}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            )}
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: '#0e0e10',
  },
  pageScrollContent: {
    minHeight: '100%',
  },
  backgroundWaves: {
    ...StyleSheet.absoluteFillObject,
    overflow: 'hidden',
    backgroundColor: '#0e0e10',
  },
  ambientBandOne: {
    position: 'absolute',
    top: 250,
    left: -180,
    width: 1700,
    height: 120,
    borderRadius: 999,
    backgroundColor: 'rgba(205,229,255,0.18)',
    opacity: 0.35,
    transform: [{ rotate: '-7deg' }],
    filter: 'blur(48px)',
  } as any,
  ambientBandTwo: {
    position: 'absolute',
    top: 360,
    left: -60,
    width: 1820,
    height: 100,
    borderRadius: 999,
    backgroundColor: 'rgba(130,209,243,0.2)',
    opacity: 0.28,
    transform: [{ rotate: '-6deg' }],
    filter: 'blur(42px)',
  } as any,
  wavePrimary: {
    position: 'absolute',
    top: 330,
    left: -120,
    width: 1680,
    height: 8,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.72)',
    boxShadow: '0 0 25px rgba(130, 209, 243, 0.5)',
    transform: [{ rotate: '-4deg' }],
  } as any,
  waveSecondary: {
    position: 'absolute',
    top: 360,
    left: -120,
    width: 1680,
    height: 6,
    borderRadius: 999,
    backgroundColor: 'rgba(141,220,255,0.78)',
    boxShadow: '0 0 40px rgba(205, 229, 255, 0.3)',
    transform: [{ rotate: '-4deg' }],
  } as any,
  waveAccentOne: {
    position: 'absolute',
    top: 430,
    left: 260,
    width: 700,
    height: 5,
    borderRadius: 999,
    backgroundColor: 'rgba(141,220,255,0.36)',
    transform: [{ rotate: '-12deg' }],
  } as any,
  waveAccentTwo: {
    position: 'absolute',
    top: 470,
    left: 360,
    width: 720,
    height: 8,
    borderRadius: 999,
    backgroundColor: 'rgba(141,220,255,0.22)',
    transform: [{ rotate: '-12deg' }],
  } as any,
  overlayFade: {
    position: 'absolute',
    inset: 0,
    backgroundColor: 'rgba(14,14,16,0.12)',
  } as any,
  pageShell: {
    flex: 1,
    width: '100%',
    maxWidth: 1376,
    alignSelf: 'center',
    paddingHorizontal: 24,
    paddingTop: 0,
    paddingBottom: 32,
    zIndex: 2,
  },
  header: {
    paddingTop: 40,
    paddingBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 20,
  },
  headerMobile: {
    flexDirection: 'column',
    alignItems: 'flex-start',
  },
  logoWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  logoBadge: {
    width: 48,
    height: 48,
    borderRadius: 16,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    boxShadow: '0 0 15px rgba(255,255,255,0.1)',
  } as any,
  logoImage: {
    width: 28,
    height: 28,
    borderRadius: 8,
  },
  logoTitle: {
    color: '#ffffff',
    fontSize: 20,
    fontWeight: '500',
    letterSpacing: 0.4,
    lineHeight: 22,
    marginBottom: 6,
  },
  logoMeta: {
    color: '#585961',
    fontSize: 11,
    fontWeight: '500',
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  headerNav: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    flexWrap: 'wrap',
  },
  glassButton: {
    minHeight: 48,
    paddingHorizontal: 24,
    borderRadius: 999,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    transitionDuration: '180ms',
  } as any,
  headerButtonText: {
    fontSize: 16,
    fontWeight: '500',
  },
  main: {
    flex: 1,
    paddingTop: 80,
    paddingBottom: 80,
  },
  heroSection: {
    maxWidth: 1000,
    alignSelf: 'center',
    alignItems: 'center',
    marginBottom: 128,
  },
  heroBadge: {
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.02)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.05)',
    marginBottom: 40,
  },
  heroBadgeText: {
    color: '#8E8E93',
    fontSize: 14,
    fontWeight: '500',
    letterSpacing: 1.2,
  },
  heroTitle: {
    color: '#ffffff',
    fontSize: 56,
    lineHeight: 64,
    fontWeight: '300',
    letterSpacing: 1.2,
    textAlign: 'center',
    marginBottom: 64,
    textShadowColor: 'rgba(0, 0, 0, 0.4)',
    textShadowOffset: { width: 0, height: 8 },
    textShadowRadius: 32,
  },
  heroTitleMobile: {
    fontSize: 36,
    lineHeight: 44,
    marginBottom: 36,
  },
  heroActions: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 24,
    flexWrap: 'wrap',
  },
  heroActionsMobile: {
    gap: 14,
  },
  downloadButton: {
    minHeight: 56,
    paddingHorizontal: 32,
    borderRadius: 999,
    backgroundColor: '#cde5ff',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    boxShadow: '0 0 24px rgba(205,229,255,0.3)',
    transitionDuration: '180ms',
  } as any,
  downloadButtonText: {
    color: '#001f2a',
    fontSize: 16,
    fontWeight: '500',
  },
  heroGlassButton: {
    minHeight: 56,
    paddingHorizontal: 32,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  heroGlassButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '500',
  },
  healthStatus: {
    marginTop: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
  },
  healthStatusText: {
    color: '#cde5ff',
    fontSize: 13,
    lineHeight: 18,
  },
  featureGrid: {
    width: '100%',
    maxWidth: 1240,
    alignSelf: 'center',
    flexDirection: 'row',
    gap: 24,
    marginBottom: 64,
  },
  featureGridMobile: {
    flexDirection: 'column',
  },
  featureCard: {
    flex: 1,
    minHeight: 240,
    padding: 32,
    borderRadius: 24,
    backgroundColor: 'rgba(22, 22, 24, 0.3)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    gap: 24,
  } as any,
  featureCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  featureCardEyebrow: {
    color: '#8ddcff',
    fontSize: 12,
    fontWeight: '500',
    letterSpacing: 2.2,
    textTransform: 'uppercase',
  },
  featureCardTitle: {
    color: '#ffffff',
    fontSize: 20,
    lineHeight: 30,
    fontWeight: '300',
    letterSpacing: 0.4,
  },
  featureCardBody: {
    color: '#8E8E93',
    fontSize: 14,
    lineHeight: 24,
    fontWeight: '300',
  },
  ragSection: {
    width: '100%',
    maxWidth: 1240,
    alignSelf: 'center',
    padding: 32,
    borderRadius: 24,
    backgroundColor: 'rgba(22, 22, 24, 0.3)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
  } as any,
  ragHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 24,
    marginBottom: 24,
  },
  ragHeaderMobile: {
    flexDirection: 'column',
    alignItems: 'flex-start',
  },
  ragHeaderMain: {
    flex: 1,
    gap: 10,
  },
  ragTitle: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '500',
    letterSpacing: 0.4,
  },
  ragDesc: {
    color: '#8E8E93',
    fontSize: 14,
    lineHeight: 22,
  },
  ragLimit: {
    color: '#8E8E93',
    fontSize: 13,
  },
  ragComposer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    paddingHorizontal: 20,
    paddingVertical: 18,
    borderRadius: 12,
    backgroundColor: 'rgba(14,14,16,0.4)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.05)',
    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.02)',
  } as any,
  ragComposerMobile: {
    alignItems: 'stretch',
  },
  ragInput: {
    flex: 1,
    color: '#ffffff',
    fontSize: 15,
    paddingHorizontal: 8,
    paddingVertical: 4,
    minHeight: 28,
    ...Platform.select({ web: { outlineStyle: 'none' } }),
  } as any,
  ragSend: {
    width: 40,
    height: 40,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(141,220,255,0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  noticeBox: {
    marginTop: 16,
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
    padding: 14,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
  },
  noticeText: {
    flex: 1,
    color: '#e5e1e4',
    fontSize: 13,
    lineHeight: 20,
  },
  resultBlock: {
    marginTop: 20,
    gap: 16,
  },
  resultTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    flexWrap: 'wrap',
  },
  resultTitle: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  resultMeta: {
    color: '#8E8E93',
    fontSize: 12,
  },
  resultAnswer: {
    color: '#e5e1e4',
    fontSize: 15,
    lineHeight: 24,
  },
  hitList: {
    gap: 12,
  },
  hitCard: {
    padding: 16,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
    gap: 8,
  },
  hitTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
  },
  hitTitle: {
    flex: 1,
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
  hitScore: {
    color: '#8ddcff',
    fontSize: 12,
    fontWeight: '600',
  },
  hitMeta: {
    color: '#8E8E93',
    fontSize: 12,
    lineHeight: 18,
  },
  hitPreview: {
    color: '#e5e1e4',
    fontSize: 13,
    lineHeight: 20,
  },
});
