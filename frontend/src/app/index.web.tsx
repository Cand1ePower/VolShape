import { useMemo, useState } from 'react';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useWindowDimensions,
} from 'react-native';

import { useThemeController } from '@/contexts/ThemeContext';
import { fetchPublicHealth, runPublicRagTest } from '@/services/public';

const APP_DOWNLOAD_URL = process.env.EXPO_PUBLIC_APP_DOWNLOAD_URL?.trim() || '';
const DEFAULT_DOWNLOAD_URL = 'https://expo.dev/go';
const APP_DOWNLOAD_HINT =
  '当前提供的是测试版入口。若你本地用 Expo Go 调试，可直接在命令行扫码进入移动端。';


const FEATURE_CARDS = [
  {
    label: '训练',
    title: '把计划生成、执行反馈、动态修正放进同一条对话里',
    body: '不需要反复切表单。用户只要描述目标、恢复状态和当天安排，系统就能持续更新训练建议。',
  },
  {
    label: '饮食',
    title: '用拍照和对话代替手动录卡路里',
    body: '识别食物、估算热量、记录三大营养素，再把结果回写到用户长期画像和后续建议里。',
  },
  {
    label: '记忆',
    title: '记住用户的身体状态、偏好变化和长期约束',
    body: '让 AI 教练不是一次性回答器，而是能随着用户状态演化的长期陪练系统。',
  },
];

function formatSourceMeta(source: { page_start?: number | null; page_end?: number | null; heading_path: string[] }) {
  const heading = source.heading_path?.slice(-2).join(' > ');
  let page = '';
  if (source.page_start) {
    page = `p.${source.page_start}`;
    if (source.page_end && source.page_end !== source.page_start) {
      page = `p.${source.page_start}-${source.page_end}`;
    }
  }

  if (heading && page) return `${heading} · ${page}`;
  return heading || page || '知识库片段';
}

export default function WebEntryPage() {
  const { width } = useWindowDimensions();
  const { isDark, toggleTheme } = useThemeController();
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthResult, setHealthResult] = useState<string>('');
  const [ragQuery, setRagQuery] = useState('DOMS 延迟性肌肉酸痛到底是什么，应该怎么恢复？');
  const [ragLoading, setRagLoading] = useState(false);
  const [ragError, setRagError] = useState('');
  const [ragResult, setRagResult] = useState<Awaited<ReturnType<typeof runPublicRagTest>> | null>(null);

  const isWide = width >= 1160;
  const isTablet = width >= 768;
  const shellWidth = isWide ? 1240 : 1040;
  const effectiveDownloadUrl = APP_DOWNLOAD_URL || DEFAULT_DOWNLOAD_URL;
  const allowDownload = !!APP_DOWNLOAD_URL;
  const pageBg = isDark ? '#09090B' : '#F3F4F6';
  const shellBg = isDark ? '#0F1117' : '#FFFFFF';
  const shellBorder = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)';

  const downloadLabel = useMemo(
    () => (allowDownload ? '下载 APP' : '下载 APP'),
    [allowDownload]
  );

  const handleHealthCheck = async () => {
    setHealthLoading(true);
    try {
      const payload = await fetchPublicHealth();
      const checks = Object.entries(payload.checks || {})
        .map(([key, value]) => `${key}: ${value}`)
        .join(' · ');
      setHealthResult(`${payload.status}${checks ? ` · ${checks}` : ''}`);
    } catch (error: any) {
      setHealthResult(error?.message || '健康检查失败');
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
        setRagError(`公开测试频率过高，请约 ${minutes} 分钟后再试。`);
      } else {
        setRagError(error?.message || '知识库测试失败');
      }
    } finally {
      setRagLoading(false);
    }
  };

  return (
    <ScrollView style={[styles.page, { backgroundColor: pageBg }]} contentContainerStyle={styles.pageContent}>
      <View style={[styles.shell, { maxWidth: shellWidth, backgroundColor: shellBg, borderColor: shellBorder }]}>
        <View style={styles.navRow}>
          <View style={styles.brandRow}>
            <Image source={require('@/assets/images/icon.png')} style={styles.brandIcon} contentFit="cover" />
            <View>
              <Text style={styles.brandName}>VolShape</Text>
              <Text style={styles.brandMeta}>AI-native 健身教练</Text>
            </View>
          </View>

          <View style={styles.navActions}>
            <TouchableOpacity
              activeOpacity={0.88}
              style={[styles.themeButton, isDark ? styles.themeButtonDark : styles.themeButtonLight]}
              onPress={toggleTheme}
            >
              <Ionicons name={isDark ? 'sunny-outline' : 'moon-outline'} size={16} color={isDark ? '#E8F2FF' : '#0F172A'} />
            </TouchableOpacity>
            <TouchableOpacity activeOpacity={0.88} style={styles.navButton} onPress={handleHealthCheck}>
              {healthLoading ? (
                <ActivityIndicator size="small" color="#E8F2FF" />
              ) : (
                <Ionicons name="pulse-outline" size={16} color="#E8F2FF" />
              )}
              <Text style={styles.navButtonText}>服务器健康</Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.9}
              style={styles.ghostButton}
              onPress={() => window.location.assign('/coach')}
            >
              <Ionicons name="open-outline" size={16} color="#D8E6FF" />
              <Text style={styles.ghostButtonText}>体验网页版</Text>
            </TouchableOpacity>
          </View>
        </View>

        <View style={styles.heroSection}>
          <View style={styles.heroTopRow}>
            <View style={styles.heroBadge}>
              <Text style={styles.heroBadgeText}>对话驱动训练、饮食、记忆闭环</Text>
            </View>
            <View style={styles.heroMiniStat}>
              <Ionicons name="sparkles-outline" size={15} color="#8BC6FF" />
              <Text style={styles.heroMiniStatText}>RAG + 记忆 + 上下文</Text>
            </View>
          </View>

          <Text style={[styles.heroTitle, isTablet ? null : styles.heroTitleCompact]}>
            只通过聊天，完成训练规划、饮食记录。
          </Text>

          <Text style={styles.heroDescription}>

          </Text>

          <View style={styles.ctaRow}>
            <TouchableOpacity
              activeOpacity={0.92}
              style={allowDownload ? styles.primaryButton : styles.primaryButtonDisabled}
              onPress={() => {
                if (Platform.OS === 'web') {
                  window.open(effectiveDownloadUrl, '_blank', 'noopener,noreferrer');
                }
              }}
            >
              <Ionicons
                name={allowDownload ? 'phone-portrait-outline' : 'qr-code-outline'}
                size={18}
                color="#07111E"
              />
              <Text style={styles.primaryButtonText}>{downloadLabel}</Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.92}
              style={styles.secondaryButton}
              onPress={() => window.location.assign('/coach')}
            >
              <Ionicons name="chatbubble-ellipses-outline" size={18} color="#EAF2FF" />
              <Text style={styles.secondaryButtonText}>体验网页版</Text>
            </TouchableOpacity>
          </View>

          <Text style={styles.downloadHint}>
            {allowDownload ? '测试包下载与网页版入口分离，方便演示与移动端体验。' : APP_DOWNLOAD_HINT}
          </Text>

          {!!healthResult && (
            <View style={styles.healthStatusCard}>
              <Ionicons name="server-outline" size={16} color="#72B7FF" />
              <Text style={styles.healthStatusText}>{healthResult}</Text>
            </View>
          )}
        </View>

        <View style={styles.featureGrid}>
          {FEATURE_CARDS.map((card) => (
            <View key={card.title} style={styles.featureCard}>
              <Text style={styles.featureLabel}>{card.label}</Text>
              <Text style={styles.featureTitle}>{card.title}</Text>
              <Text style={styles.featureBody}>{card.body}</Text>
            </View>
          ))}
        </View>

        <View style={styles.ragSection}>
          <View style={styles.ragSectionHeader}>
            <View>
              <Text style={styles.ragEyebrow}>RAG 知识库测试</Text>
            </View>
            <Text style={styles.ragLimitText}>每 5 分钟最多 10 次</Text>
          </View>

          <Text style={styles.ragDescription}>
            这里走的是项目当前专家模式使用的知识库链路：runtime artifact + Qdrant 向量检索 + BM25 关键词召回 +
            本地融合重排。
          </Text>

          <View style={styles.ragComposer}>
            <TextInput
              multiline
              value={ragQuery}
              onChangeText={setRagQuery}
              placeholder="输入一个训练、恢复、营养相关的问题"
              placeholderTextColor="#7488A5"
              style={styles.ragInput}
            />

            <TouchableOpacity
              activeOpacity={0.92}
              style={[styles.ragSubmitButton, ragLoading ? styles.ragSubmitButtonDisabled : null]}
              disabled={ragLoading}
              onPress={handleRagTest}
            >
              {ragLoading ? (
                <ActivityIndicator size="small" color="#05111D" />
              ) : (
                <Ionicons name="search-outline" size={16} color="#05111D" />
              )}
              <Text style={styles.ragSubmitText}>测试知识库</Text>
            </TouchableOpacity>
          </View>

          {!!ragError && (
            <View style={styles.errorCard}>
              <Ionicons name="alert-circle-outline" size={18} color="#FFB3A7" />
              <Text style={styles.errorCardText}>{ragError}</Text>
            </View>
          )}

          {!!ragResult && (
            <View style={styles.ragResultShell}>
              <View style={styles.ragResultHeader}>
                <Text style={styles.ragResultTitle}>知识库回答</Text>
                <Text style={styles.ragResultMeta}>
                  {ragResult.retrieval_mode} · {ragResult.hit_count} hits
                </Text>
              </View>

              <Text style={ragResult.answer ? styles.ragAnswer : styles.ragAnswerMuted}>
                {ragResult.answer || '本次未生成总结回答，下面展示召回到的证据片段。'}
              </Text>

              {ragResult.llm_degraded && (
                <View style={styles.degradedNotice}>
                  <Ionicons name="warning-outline" size={16} color="#F9DEA6" />
                  <Text style={styles.degradedNoticeText}>
                    本次回答降级为检索结果展示。原因：{ragResult.llm_error || 'LLM 不可用'}
                  </Text>
                </View>
              )}

              {!!ragResult.sources?.length && (
                <View style={styles.sourceList}>
                  {ragResult.sources.map((source) => (
                    <View key={source} style={styles.sourceChip}>
                      <Text style={styles.sourceChipText}>{source}</Text>
                    </View>
                  ))}
                </View>
              )}

              {!!ragResult.hits?.length && (
                <View style={styles.hitList}>
                  {ragResult.hits.map((hit, index) => (
                    <View key={`${hit.title}-${index}`} style={styles.hitCard}>
                      <View style={styles.hitCardTop}>
                        <Text style={styles.hitCardTitle}>{hit.title}</Text>
                        <Text style={styles.hitCardScore}>{hit.score.toFixed(2)}</Text>
                      </View>
                      <Text style={styles.hitCardMeta}>
                        {formatSourceMeta(hit)} · {hit.source_type} · {hit.score_type}
                      </Text>
                      <Text style={styles.hitCardPreview}>{hit.preview}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: '#08101A',
  },
  pageContent: {
    paddingHorizontal: 20,
    paddingTop: 28,
    paddingBottom: 48,
  },
  shell: {
    width: '100%',
    alignSelf: 'center',
    gap: 18,
  },
  navRow: {
    minHeight: 74,
    borderRadius: 24,
    borderWidth: 0.5,
    borderColor: 'rgba(126, 160, 221, 0.18)',
    backgroundColor: 'rgba(8, 16, 27, 0.92)',
    paddingHorizontal: 18,
    paddingVertical: 14,
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  brandIcon: {
    width: 54,
    height: 54,
    borderRadius: 16,
  },
  brandName: {
    color: '#F7FAFF',
    fontSize: 18,
    fontWeight: '800',
  },
  brandMeta: {
    marginTop: 3,
    color: '#91A6C6',
    fontSize: 12,
  },
  navActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 10,
  },
  themeButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 0.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  themeButtonDark: {
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderColor: 'rgba(255,255,255,0.12)',
  },
  themeButtonLight: {
    backgroundColor: 'rgba(15,23,42,0.04)',
    borderColor: 'rgba(15,23,42,0.10)',
  },
  navButton: {
    height: 40,
    paddingHorizontal: 14,
    borderRadius: 20,
    backgroundColor: 'rgba(22, 42, 69, 0.96)',
    borderWidth: 0.5,
    borderColor: 'rgba(121, 164, 231, 0.18)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  navButtonText: {
    color: '#E8F2FF',
    fontSize: 13,
    fontWeight: '700',
  },
  ghostButton: {
    height: 40,
    paddingHorizontal: 14,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.12)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  ghostButtonText: {
    color: '#D8E6FF',
    fontSize: 13,
    fontWeight: '700',
  },
  heroSection: {
    borderRadius: 34,
    borderWidth: 0.5,
    borderColor: 'rgba(132, 165, 230, 0.18)',
    backgroundColor: 'rgba(8, 16, 28, 0.96)',
    paddingHorizontal: 26,
    paddingVertical: 28,
    gap: 18,
  },
  heroTopRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
  },
  heroBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: 'rgba(102, 201, 255, 0.12)',
    borderWidth: 0.5,
    borderColor: 'rgba(102, 201, 255, 0.22)',
  },
  heroBadgeText: {
    color: '#8BD3FF',
    fontSize: 12,
    fontWeight: '700',
  },
  heroMiniStat: {
    minHeight: 38,
    paddingHorizontal: 12,
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.1)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  heroMiniStatText: {
    color: '#C7D8F1',
    fontSize: 12,
    fontWeight: '600',
  },
  heroTitle: {
    color: '#F6FAFF',
    fontSize: 48,
    lineHeight: 58,
    fontWeight: '900',
    maxWidth: 940,
  },
  heroTitleCompact: {
    fontSize: 36,
    lineHeight: 46,
  },
  heroDescription: {
    color: '#B4C3D8',
    fontSize: 16,
    lineHeight: 27,
    maxWidth: 980,
  },
  heroBulletList: {
    gap: 12,
  },
  heroBullet: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  heroBulletText: {
    flex: 1,
    color: '#DDE7F5',
    fontSize: 15,
    lineHeight: 23,
    fontWeight: '600',
  },
  ctaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    alignItems: 'center',
  },
  primaryButton: {
    minHeight: 50,
    paddingHorizontal: 18,
    borderRadius: 16,
    backgroundColor: '#8DDCFF',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  primaryButtonDisabled: {
    minHeight: 50,
    paddingHorizontal: 18,
    borderRadius: 16,
    backgroundColor: '#8DDCFF',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
    opacity: 0.86,
  },
  primaryButtonText: {
    color: '#07111E',
    fontSize: 14,
    fontWeight: '800',
  },
  secondaryButton: {
    minHeight: 50,
    paddingHorizontal: 18,
    borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.14)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 9,
  },
  secondaryButtonText: {
    color: '#EAF2FF',
    fontSize: 14,
    fontWeight: '800',
  },
  downloadHint: {
    color: '#8091AB',
    fontSize: 12,
    lineHeight: 18,
  },
  healthStatusCard: {
    minHeight: 42,
    borderRadius: 15,
    backgroundColor: 'rgba(20, 33, 48, 0.92)',
    borderWidth: 0.5,
    borderColor: 'rgba(114, 183, 255, 0.18)',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 13,
    paddingVertical: 10,
  },
  healthStatusText: {
    flex: 1,
    color: '#D7E6FA',
    fontSize: 13,
    lineHeight: 19,
    fontWeight: '600',
  },
  featureGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
  },
  featureCard: {
    flex: 1,
    minWidth: 280,
    borderRadius: 24,
    borderWidth: 0.5,
    borderColor: 'rgba(147, 178, 233, 0.14)',
    backgroundColor: 'rgba(9, 18, 30, 0.88)',
    padding: 18,
    gap: 8,
  },
  featureLabel: {
    color: '#7EC9FF',
    fontSize: 11,
    fontWeight: '800',
  },
  featureTitle: {
    color: '#F4F8FF',
    fontSize: 18,
    lineHeight: 24,
    fontWeight: '800',
  },
  featureBody: {
    color: '#A9B8CD',
    fontSize: 13,
    lineHeight: 21,
  },
  infoBand: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
  },
  infoCard: {
    flex: 1,
    minWidth: 280,
    borderRadius: 24,
    borderWidth: 0.5,
    borderColor: 'rgba(147, 178, 233, 0.14)',
    backgroundColor: 'rgba(9, 18, 30, 0.88)',
    padding: 18,
    gap: 8,
  },
  infoCardLabel: {
    color: '#7EC9FF',
    fontSize: 11,
    fontWeight: '800',
  },
  infoCardTitle: {
    color: '#F4F8FF',
    fontSize: 18,
    lineHeight: 24,
    fontWeight: '800',
  },
  infoCardBody: {
    color: '#A8B7CB',
    fontSize: 13,
    lineHeight: 21,
  },
  ragSection: {
    borderRadius: 28,
    borderWidth: 0.5,
    borderColor: 'rgba(150, 181, 234, 0.16)',
    backgroundColor: 'rgba(8, 15, 24, 0.96)',
    padding: 18,
    gap: 14,
  },
  ragSectionHeader: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  ragEyebrow: {
    color: '#7ED7FF',
    fontSize: 11,
    fontWeight: '800',
    marginBottom: 4,
  },
  ragTitle: {
    color: '#F5F8FD',
    fontSize: 24,
    lineHeight: 30,
    fontWeight: '900',
  },
  ragLimitText: {
    color: '#90A6C7',
    fontSize: 12,
    fontWeight: '700',
  },
  ragDescription: {
    color: '#A8B8CE',
    fontSize: 13,
    lineHeight: 21,
    maxWidth: 860,
  },
  ragComposer: {
    borderRadius: 22,
    borderWidth: 0.5,
    borderColor: 'rgba(144, 177, 230, 0.16)',
    backgroundColor: 'rgba(255,255,255,0.03)',
    padding: 12,
    gap: 10,
  },
  ragInput: {
    minHeight: 76,
    color: '#F1F6FF',
    fontSize: 15,
    lineHeight: 22,
    paddingHorizontal: 4,
    paddingVertical: 4,
    textAlignVertical: 'top',
    ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as any) : {}),
  },
  ragSubmitButton: {
    alignSelf: 'flex-start',
    minHeight: 40,
    paddingHorizontal: 14,
    borderRadius: 14,
    backgroundColor: '#7FDBFF',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  ragSubmitButtonDisabled: {
    opacity: 0.72,
  },
  ragSubmitText: {
    color: '#05111D',
    fontSize: 13,
    fontWeight: '800',
  },
  errorCard: {
    borderRadius: 16,
    backgroundColor: 'rgba(74, 28, 24, 0.45)',
    borderWidth: 0.5,
    borderColor: 'rgba(255, 145, 128, 0.22)',
    paddingHorizontal: 13,
    paddingVertical: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  errorCardText: {
    flex: 1,
    color: '#FFD5CC',
    fontSize: 13,
    lineHeight: 19,
    fontWeight: '600',
  },
  ragResultShell: {
    gap: 12,
    borderRadius: 22,
    borderWidth: 0.5,
    borderColor: 'rgba(141, 171, 226, 0.14)',
    backgroundColor: 'rgba(13, 21, 31, 0.94)',
    padding: 14,
  },
  ragResultHeader: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 8,
    alignItems: 'center',
  },
  ragResultTitle: {
    color: '#F3F7FE',
    fontSize: 15,
    fontWeight: '800',
  },
  ragResultMeta: {
    color: '#86A1C5',
    fontSize: 12,
    fontWeight: '700',
  },
  ragAnswer: {
    color: '#EAF3FF',
    fontSize: 14,
    lineHeight: 23,
    fontWeight: '600',
  },
  ragAnswerMuted: {
    color: '#97AAC7',
    fontSize: 13,
    lineHeight: 20,
    fontWeight: '600',
  },
  degradedNotice: {
    borderRadius: 14,
    backgroundColor: 'rgba(89, 69, 23, 0.28)',
    borderWidth: 0.5,
    borderColor: 'rgba(245, 201, 122, 0.18)',
    paddingHorizontal: 12,
    paddingVertical: 9,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  degradedNoticeText: {
    flex: 1,
    color: '#F9DEA6',
    fontSize: 12,
    lineHeight: 18,
    fontWeight: '600',
  },
  sourceList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  sourceChip: {
    borderRadius: 999,
    backgroundColor: 'rgba(114, 183, 255, 0.1)',
    borderWidth: 0.5,
    borderColor: 'rgba(114, 183, 255, 0.16)',
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  sourceChipText: {
    color: '#CFE3FF',
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '700',
  },
  hitList: {
    gap: 10,
  },
  hitCard: {
    borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.03)',
    borderWidth: 0.5,
    borderColor: 'rgba(140, 171, 224, 0.12)',
    padding: 12,
    gap: 6,
  },
  hitCardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
  },
  hitCardTitle: {
    flex: 1,
    color: '#F1F6FF',
    fontSize: 13,
    fontWeight: '800',
  },
  hitCardScore: {
    color: '#7DC9FF',
    fontSize: 12,
    fontWeight: '800',
  },
  hitCardMeta: {
    color: '#92A8C5',
    fontSize: 11,
    lineHeight: 16,
    fontWeight: '700',
  },
  hitCardPreview: {
    color: '#C2D2E6',
    fontSize: 12,
    lineHeight: 19,
  },
});
