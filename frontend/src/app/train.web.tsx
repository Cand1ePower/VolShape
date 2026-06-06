import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useColorScheme, useWindowDimensions, Animated, Modal, ActivityIndicator, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePlan, CompletedPlan } from '@/contexts/PlanContext';
import { useAuth } from '@/contexts/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { getBackendBaseUrl } from '@/services/api';

const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

function formatDate(d: Date): string {
  try {
    const dateObj = typeof d === 'string' ? new Date(d) : d;
    return `${MONTHS[dateObj.getMonth()]}${dateObj.getDate()}日 ${String(dateObj.getHours()).padStart(2, '0')}:${String(dateObj.getMinutes()).padStart(2, '0')}`;
  } catch {
    return '今日训练';
  }
}

// HistoryCard
function HistoryCard({ 
  plan, 
  isDark, 
  borderCol, 
  textCol, 
  subTextCol, 
  isExpanded, 
  onPress 
}: { 
  plan: CompletedPlan; 
  isDark: boolean; 
  borderCol: string; 
  textCol: string; 
  subTextCol: string; 
  isExpanded: boolean; 
  onPress: () => void; 
}) {
  const done = plan.completedSets >= plan.totalSets;
  
  const expandAnim = React.useRef(new Animated.Value(isExpanded ? 1 : 0)).current;

  React.useEffect(() => {
    Animated.spring(expandAnim, {
      toValue: isExpanded ? 1 : 0,
      damping: 15,
      stiffness: 95,
      useNativeDriver: false,
    }).start();
  }, [isExpanded]);

  const summaryOpacity = expandAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 0]
  });
  const summaryHeight = expandAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [72, 0]
  });

  const detailOpacity = expandAnim.interpolate({
    inputRange: [0, 0.3, 1],
    outputRange: [0, 0, 1]
  });
  const detailHeight = expandAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, plan.exercises.length * 68 + 48]
  });

  return (
    <View style={styles.timelineRow}>
      <View style={styles.timelineLeft}>
        <View style={[styles.timelineLine, { backgroundColor: borderCol }]} />
        <View style={[styles.timelineDot, { backgroundColor: done ? '#34C759' : '#FF9500' }]} />
      </View>
      
      <TouchableOpacity 
        activeOpacity={0.85} 
        onPress={onPress} 
        style={styles.timelineRight}
      >
        <LinearGradient
          colors={isDark 
            ? ['rgba(28, 28, 30, 0.95)', 'rgba(28, 28, 30, 0.45)'] 
            : ['rgba(255, 255, 255, 0.98)', 'rgba(255, 255, 255, 0.55)']
          }
          style={[styles.historyCard, { borderColor: borderCol }]}
        >
          <View style={styles.historyContent}>
            <View style={styles.historyHeader}>
              <Text style={[styles.historyTitle, { color: textCol }]}>{formatDate(plan.completedAt)}</Text>
              <View style={[styles.historyBadge, { backgroundColor: done ? 'rgba(52,199,89,0.12)' : 'rgba(255,149,0,0.12)' }]}>
                <Text style={[styles.historyBadgeText, { color: done ? '#34C759' : '#FF9500' }]}>
                  {done ? '✓ 完成' : `${plan.completedSets}/${plan.totalSets}`}
                </Text>
              </View>
            </View>
            <Text style={[styles.historyMeta, { color: subTextCol }]}>
              {plan.exercises.length} 个动作 · {plan.totalSets} 组
            </Text>
            
            <Animated.View style={{ 
              opacity: summaryOpacity, 
              maxHeight: summaryHeight, 
              overflow: 'hidden' 
            }}>
              <View style={styles.historyExercises}>
                {plan.exercises.slice(0, 3).map((ex, i) => (
                  <Text key={i} style={[styles.historyExItem, { color: subTextCol }]}>
                    {ex.name} {ex.sets}×{ex.reps}
                  </Text>
                ))}
                {plan.exercises.length > 3 && (
                  <Text style={[styles.historyExItem, { color: subTextCol }]}>+{plan.exercises.length - 3} 更多...</Text>
                )}
              </View>
            </Animated.View>

            <Animated.View style={{ 
              opacity: detailOpacity, 
              maxHeight: detailHeight, 
              overflow: 'hidden' 
            }}>
              <View style={styles.expandedContent}>
                <View style={[styles.expandedDivider, { backgroundColor: borderCol }]} />
                <Text style={[styles.detailTitle, { color: textCol }]}>动作明细：</Text>
                {plan.exercises.map((ex, exIdx) => {
                  const completedForEx = plan.completedKeys?.filter(k => k.startsWith(`${exIdx}-`)).length || 0;
                  const ratio = ex.sets > 0 ? Math.min(completedForEx / ex.sets, 1) : 0;
                  
                  return (
                    <View key={exIdx} style={[styles.detailRow, { borderColor: borderCol, backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)' }]}>
                      <View style={[styles.detailProgressFill, { width: `${ratio * 100}%` }]} />
                      <View style={styles.detailRowInner}>
                        <View style={[styles.detailExNum, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)' }]}>
                          <Text style={{ fontSize: 9, fontWeight: '700', color: textCol }}>{exIdx + 1}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 13, fontWeight: '700', color: textCol, marginBottom: 2 }}>{ex.name}</Text>
                          <Text style={{ fontSize: 11, color: subTextCol }}>计划: {ex.sets} 组 × {ex.reps}{ex.weight ? ` · ${ex.weight}` : ''}</Text>
                        </View>
                        <Text style={{ fontSize: 12, fontWeight: '700', color: ratio === 1 ? '#34C759' : textCol }}>
                          {completedForEx}/{ex.sets}
                        </Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            </Animated.View>
          </View>
        </LinearGradient>
      </TouchableOpacity>
    </View>
  );
}

export default function TrainScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const [isWebMounted, setIsWebMounted] = React.useState(Platform.OS !== 'web');
  const { activePlan, completedExercises, toggleComplete, completePlan, resetPlan, trainingHistory } = usePlan();
  const { token } = useAuth();
  const isWeb = Platform.OS === 'web';
  const isDesktopWeb = isWebMounted && isWeb && width >= 1100;
  const contentMaxWidth = isDesktopWeb ? 1040 : 820;

  // History detail inline expanded state (Accordion Mode)
  const [expandedPlanIdx, setExpandedPlanIdx] = React.useState<number | null>(null);

  // Abandoned history modal states
  const [abandonedPlans, setAbandonedPlans] = React.useState<CompletedPlan[]>([]);
  const [showAbandonedModal, setShowAbandonedModal] = React.useState(false);
  const [isLoadingAbandoned, setIsLoadingAbandoned] = React.useState(false);

  const handleFetchAbandoned = async () => {
    setIsLoadingAbandoned(true);
    setShowAbandonedModal(true);
    try {
      const baseUrl = getBackendBaseUrl();
      const resp = await fetch(`${baseUrl}/api/workout/abandoned_history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.history) {
          const list = data.history.map((p: any) => ({
            planId: p.id,
            title: p.plan_json.title || '被放弃的计划',
            exercises: p.plan_json.exercises || [],
            disclaimer: p.plan_json.disclaimer,
            createdAt: new Date(p.target_date),
            completedAt: new Date(p.target_date),
            completedSets: p.completion_data?.completed_sets || 0,
            totalSets: p.completion_data?.total_sets || 0,
          }));
          setAbandonedPlans(list);
        }
      }
    } catch (e) {
      console.error('[Fetch Abandoned Error]', e);
    } finally {
      setIsLoadingAbandoned(false);
    }
  };

  const isSetPlayable = (exIdx: number, setIdx: number) => {
    if (setIdx === 0) {
      if (completedExercises.has(`${exIdx}-0`)) {
        return !completedExercises.has(`${exIdx}-1`);
      }
      return true;
    }
    
    const prevKey = `${exIdx}-${setIdx - 1}`;
    const currentKey = `${exIdx}-${setIdx}`;
    const nextKey = `${exIdx}-${setIdx + 1}`;
    
    if (completedExercises.has(currentKey)) {
      return !completedExercises.has(nextKey);
    } else {
      return completedExercises.has(prevKey);
    }
  };

  const bgCol = isDark ? '#0A0A0C' : '#F5F5F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFFFFF';
  const borderCol = isDark ? '#2C2C2E' : '#E5E5EA';
  const textCol = isDark ? '#FFFFFF' : '#1C1C1E';
  const subTextCol = isDark ? '#AEAEB2' : '#8E8E93';
  const accentCol = '#007AFF';
  const successCol = '#34C759';

  const totalSets = activePlan ? activePlan.exercises.reduce((sum, ex) => sum + ex.sets, 0) : 0;
  const completedCount = completedExercises.size;
  const progress = totalSets > 0 ? completedCount / totalSets : 0;

  const hasHistory = trainingHistory.length > 0;

  React.useEffect(() => {
    if (Platform.OS === 'web') {
      setIsWebMounted(true);
    }
  }, []);

  if (!activePlan && !hasHistory) {
    return (
      <View style={[styles.container, { backgroundColor: bgCol, paddingTop: insets.top + 20 }]}>
        <View style={styles.emptyState}>
          <Text style={styles.emptyIcon}>🏋️</Text>
          <Text style={[styles.emptyTitle, { color: textCol }]}>暂无训练计划</Text>
          <Text style={[styles.emptySub, { color: subTextCol }]}>
            在聊天页让 AI 教练为你生成训练计划，{'\n'}点击"应用计划"即可在此开始训练。
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: bgCol }]}>
      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          {
            paddingTop: insets.top + 16,
            paddingBottom: insets.bottom + 120,
            paddingHorizontal: isDesktopWeb ? 28 : 16,
          },
        ]}
        contentInsetAdjustmentBehavior="automatic"
      >
        <View style={[styles.pageFrame, { maxWidth: contentMaxWidth }]}>
        {/* Active Plan */}
        {activePlan && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: textCol }]}>当前训练</Text>
            <View style={styles.header}>
              <Text style={[styles.title, { color: textCol }]}>{activePlan.title}</Text>
              {activePlan.disclaimer && (
                <View style={[styles.disclaimerBox, { backgroundColor: 'rgba(255, 149, 0, 0.1)' }]}>
                  <Text style={[styles.disclaimerText, { color: '#FF9500' }]}>{activePlan.disclaimer}</Text>
                </View>
              )}
              <View style={[styles.progressBar, { backgroundColor: isDark ? '#2C2C2E' : '#E5E5EA' }]}>
                <View style={[styles.progressFill, { width: `${progress * 100}%`, backgroundColor: successCol }]} />
              </View>
              <Text style={[styles.progressText, { color: subTextCol }]}>
                {completedCount} / {totalSets} 组完成
              </Text>
            </View>

            {activePlan.exercises.map((exercise, exIdx) => (
              <View key={exIdx} style={[styles.exerciseCard, { backgroundColor: cardBg, borderColor: borderCol }]}>
                <View style={styles.exerciseHeader}>
                  <View style={[styles.exNum, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)' }]}>
                    <Text style={[styles.exNumText, { color: textCol }]}>{exIdx + 1}</Text>
                  </View>
                  <View style={styles.exInfo}>
                    <Text style={[styles.exName, { color: textCol }]}>{exercise.name}</Text>
                    <Text style={[styles.exMeta, { color: subTextCol }]}>
                      {exercise.sets} 组 × {exercise.reps}{exercise.weight ? ` · ${exercise.weight}` : ''}
                    </Text>
                  </View>
                </View>
                {exercise.notes && <Text style={[styles.exNotes, { color: subTextCol }]}>{exercise.notes}</Text>}
                <View style={styles.setRow}>
                  {Array.from({ length: exercise.sets }).map((_, setIdx) => {
                    const key = `${exIdx}-${setIdx}`;
                    const done = completedExercises.has(key);
                    const playable = isSetPlayable(exIdx, setIdx);
                    
                    return (
                      <TouchableOpacity 
                        key={setIdx} 
                        activeOpacity={playable ? 0.7 : 1} 
                        disabled={!playable}
                        onPress={() => toggleComplete(exIdx, setIdx)}
                        style={[styles.setChip, {
                          borderColor: done ? successCol : playable ? borderCol : (isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'),
                          backgroundColor: done 
                            ? 'rgba(52, 199, 89, 0.15)' 
                            : 'transparent',
                          opacity: playable ? 1 : 0.35,
                        }]}>
                        <Text style={[styles.setChipText, { color: done ? successCol : playable ? textCol : subTextCol }]}>
                          {!playable ? '🔒 ' : done ? '✓ ' : '○ '}第{setIdx + 1}组
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            ))}

            <View style={styles.actionRow}>
              <TouchableOpacity activeOpacity={0.8} style={[styles.finishBtn, { backgroundColor: accentCol }]} onPress={completePlan}>
                <Text style={styles.finishBtnText}>✅ 完成训练</Text>
              </TouchableOpacity>
              <TouchableOpacity activeOpacity={0.8} style={[styles.cancelBtn, { borderColor: borderCol }]} onPress={resetPlan}>
                <Text style={[styles.cancelBtnText, { color: subTextCol }]}>放弃</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* Training History Timeline */}
        {hasHistory && (
          <View style={styles.section}>
            <View style={styles.historyTitleRow}>
              <Text style={[styles.sectionTitle, { color: textCol, marginBottom: 0 }]}>训练历史</Text>
              <TouchableOpacity 
                activeOpacity={0.7} 
                onPress={handleFetchAbandoned} 
                style={styles.abandonedIconBtn}
              >
                <Ionicons name="archive-outline" size={15} color={subTextCol} style={{ marginRight: 4 }} />
                <Text style={[styles.abandonedBtnText, { color: subTextCol }]}>已放弃</Text>
              </TouchableOpacity>
            </View>
            
            <View style={styles.timeline}>
              {trainingHistory.map((plan, idx) => (
                <HistoryCard 
                  key={idx} 
                  plan={plan} 
                  isDark={isDark} 
                  borderCol={borderCol} 
                  textCol={textCol} 
                  subTextCol={subTextCol} 
                  isExpanded={expandedPlanIdx === idx}
                  onPress={() => setExpandedPlanIdx((prev) => (prev === idx ? null : idx))}
                />
              ))}
            </View>
          </View>
        )}
        </View>
      </ScrollView>

      {/* 已放弃计划列表 Modal (大厂半透明毛玻璃微光) */}
      {showAbandonedModal && (
        <Modal animationType="fade" transparent visible={showAbandonedModal} onRequestClose={() => setShowAbandonedModal(false)}>
          <View style={styles.modalOverlay}>
            <View style={[styles.modalContent, { backgroundColor: isDark ? 'rgba(28,28,30,0.94)' : 'rgba(255,255,255,0.96)', borderColor: borderCol }]}>
              <View style={styles.modalHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.modalTitle, { color: textCol }]}>已放弃的计划</Text>
                  <Text style={{ fontSize: 11, color: subTextCol, marginTop: 4 }}>查看您之前创建但选择放弃的计划</Text>
                </View>
                <TouchableOpacity activeOpacity={0.7} style={[styles.closeBtn, { backgroundColor: isDark ? '#2C2C30' : '#E5E5EA' }]} onPress={() => setShowAbandonedModal(false)}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: textCol }}>✕</Text>
                </TouchableOpacity>
              </View>

              <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
                {isLoadingAbandoned ? (
                  <ActivityIndicator size="large" color={accentCol} style={{ marginTop: 50 }} />
                ) : abandonedPlans.length === 0 ? (
                  <Text style={{ textAlign: 'center', color: subTextCol, marginTop: 50, fontSize: 13 }}>暂无已放弃的计划记录</Text>
                ) : (
                  abandonedPlans.map((item, idx) => (
                    <View key={idx} style={[styles.abandonedCard, { borderColor: borderCol, backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)' }]}>
                      <View style={styles.abandonedCardHeader}>
                        <Text style={{ fontSize: 13, fontWeight: '800', color: textCol }}>{formatDate(item.createdAt)}</Text>
                        <View style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5, backgroundColor: 'rgba(255,59,48,0.12)' }}>
                          <Text style={{ fontSize: 9, color: '#FF3B30', fontWeight: '800' }}>已放弃</Text>
                        </View>
                      </View>
                      <View style={{ marginTop: 8, gap: 4 }}>
                        {item.exercises.map((ex, exIdx) => (
                          <Text key={exIdx} style={{ fontSize: 11, color: subTextCol, lineHeight: 16 }}>
                            • {ex.name} ({ex.sets}组 × {ex.reps})
                          </Text>
                        ))}
                      </View>
                    </View>
                  ))
                )}
              </ScrollView>

              <TouchableOpacity activeOpacity={0.7} style={{ margin: 16, paddingVertical: 13, borderRadius: 12, backgroundColor: accentCol, alignItems: 'center' }} onPress={() => setShowAbandonedModal(false)}>
                <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 14 }}>关闭</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { paddingHorizontal: 16 },
  pageFrame: { width: '100%', alignSelf: 'center' },
  section: { marginBottom: 18 },
  sectionTitle: { fontSize: 16, fontWeight: '800', marginBottom: 10, letterSpacing: -0.4 },
  header: { marginBottom: 14 },
  title: { fontSize: 20, fontWeight: '800', letterSpacing: -0.6, marginBottom: 8 },
  disclaimerBox: { borderRadius: 8, padding: 10, marginBottom: 10 },
  disclaimerText: { fontSize: 11, fontWeight: '600', lineHeight: 16 },
  progressBar: { height: 6, borderRadius: 3, marginBottom: 6, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 3 },
  progressText: { fontSize: 12, fontWeight: '600' },
  exerciseCard: { borderRadius: 12, borderWidth: 0.5, padding: 12, marginBottom: 10 },
  exerciseHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
  exNum: { width: 24, height: 24, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  exNumText: { fontSize: 12, fontWeight: '700' },
  exInfo: { flex: 1 },
  exName: { fontSize: 15, fontWeight: '700', marginBottom: 1 },
  exMeta: { fontSize: 12 },
  exNotes: { fontSize: 11, fontStyle: 'italic', marginBottom: 8, paddingLeft: 34 },
  setRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingLeft: 34 },
  setChip: { borderWidth: 0.5, borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10 },
  setChipText: { fontSize: 12, fontWeight: '600' },
  actionRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  finishBtn: { flex: 1, borderRadius: 12, paddingVertical: 12, alignItems: 'center' },
  finishBtnText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
  cancelBtn: { borderRadius: 12, paddingVertical: 12, paddingHorizontal: 16, alignItems: 'center', borderWidth: 0.5 },
  cancelBtnText: { fontSize: 13, fontWeight: '600' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 30 },
  emptyIcon: { fontSize: 40, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '700', marginBottom: 6 },
  emptySub: { fontSize: 13, textAlign: 'center', lineHeight: 20 },
  
  // Timeline (极致优化贯通，无Margin截断)
  timeline: { gap: 0 },
  timelineRow: { flexDirection: 'row', width: '100%', marginBottom: 0 }, // 彻底将外边距归 0，实现竖线垂直衔接
  timelineLeft: { width: 28, alignItems: 'center', position: 'relative' },
  timelineLine: { position: 'absolute', left: 13, top: 0, bottom: 0, width: 1.5 }, // 从 top: 0 直通 bottom: 0 贯穿
  timelineDot: { width: 10, height: 10, borderRadius: 5, marginTop: 18, zIndex: 2 },
  timelineRight: { flex: 1, paddingBottom: 12 }, // 通过右栏的 padding 维持卡片之间的呼吸间距，实现贯穿
  historyCard: { borderRadius: 16, borderWidth: 0.5, overflow: 'hidden' },
  historyContent: { padding: 14 },
  historyHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  historyTitle: { fontSize: 14, fontWeight: '800', flex: 1 },
  historyBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, marginLeft: 8 },
  historyBadgeText: { fontSize: 9, fontWeight: '800' },
  historyMeta: { fontSize: 11, marginBottom: 8, fontWeight: '500' },
  historyExercises: { gap: 4 },
  historyExItem: { fontSize: 11, fontWeight: '500' },
  
  // 原位展开手风琴明细样式
  expandedContent: { marginTop: 12 },
  expandedDivider: { height: 0.5, marginBottom: 12, opacity: 0.6 },
  detailTitle: { fontSize: 12, fontWeight: '800', marginBottom: 8, letterSpacing: -0.2 },
  detailRow: { borderRadius: 10, borderWidth: 0.5, marginBottom: 8, overflow: 'hidden', position: 'relative' },
  detailProgressFill: { position: 'absolute', top: 0, bottom: 0, left: 0, backgroundColor: 'rgba(52, 199, 89, 0.12)' },
  detailRowInner: { padding: 10, flexDirection: 'row', alignItems: 'center' },
  detailExNum: { width: 18, height: 18, borderRadius: 9, justifyContent: 'center', alignItems: 'center', marginRight: 8 },

  // 已放弃标题行与归档卡片
  historyTitleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  abandonedIconBtn: { flexDirection: 'row', alignItems: 'center', paddingVertical: 4, paddingHorizontal: 10, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.06)' },
  abandonedBtnText: { fontSize: 11, fontWeight: '700' },
  abandonedCard: { borderRadius: 12, borderWidth: 0.5, padding: 12, marginBottom: 10, overflow: 'hidden' },
  abandonedCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },

  // Modals
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { width: '100%', maxWidth: 440, height: '70%', borderRadius: 20, borderWidth: 0.5, overflow: 'hidden' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 0.5, borderBottomColor: '#2C2C2E' },
  modalTitle: { fontSize: 16, fontWeight: '800', letterSpacing: -0.4 },
  closeBtn: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
});
