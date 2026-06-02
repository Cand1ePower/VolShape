import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useColorScheme, useWindowDimensions, Modal } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePlan, CompletedPlan } from '@/contexts/PlanContext';

const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

function formatDate(d: Date): string {
  try {
    const dateObj = typeof d === 'string' ? new Date(d) : d;
    return `${MONTHS[dateObj.getMonth()]}${dateObj.getDate()}日 ${String(dateObj.getHours()).padStart(2, '0')}:${String(dateObj.getMinutes()).padStart(2, '0')}`;
  } catch {
    return '今日训练';
  }
}

function HistoryCard({ plan, isDark, bg, border, text, sub, onPress }: { plan: CompletedPlan; isDark: boolean; bg: string; border: string; text: string; sub: string; onPress: () => void }) {
  const done = plan.completedSets >= plan.totalSets;
  return (
    <TouchableOpacity activeOpacity={0.7} onPress={onPress} style={[styles.historyCard, { backgroundColor: bg, borderColor: border }]}>
      <View style={styles.historyLeft}>
        <View style={[styles.historyDot, { backgroundColor: done ? '#34C759' : '#FF9500' }]} />
        <View style={[styles.historyLine, { backgroundColor: border }]} />
      </View>
      <View style={styles.historyContent}>
        <View style={styles.historyHeader}>
          <Text style={[styles.historyTitle, { color: text }]}>{plan.title}</Text>
          <View style={[styles.historyBadge, { backgroundColor: done ? 'rgba(52,199,89,0.12)' : 'rgba(255,149,0,0.12)' }]}>
            <Text style={[styles.historyBadgeText, { color: done ? '#34C759' : '#FF9500' }]}>
              {done ? '✓ 完成' : `${plan.completedSets}/${plan.totalSets}`}
            </Text>
          </View>
        </View>
        <Text style={[styles.historyMeta, { color: sub }]}>
          {formatDate(plan.completedAt)} · {plan.exercises.length} 个动作 · {plan.totalSets} 组
        </Text>
        <View style={styles.historyExercises}>
          {plan.exercises.slice(0, 3).map((ex, i) => (
            <Text key={i} style={[styles.historyExItem, { color: sub }]}>
              {ex.name} {ex.sets}×{ex.reps}
            </Text>
          ))}
          {plan.exercises.length > 3 && (
            <Text style={[styles.historyExItem, { color: sub }]}>+{plan.exercises.length - 3} 更多...</Text>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
}

export default function TrainScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { activePlan, completedExercises, toggleComplete, completePlan, resetPlan, trainingHistory } = usePlan();

  // History detail modal state
  const [selectedPlan, setSelectedPlan] = React.useState<CompletedPlan | null>(null);

  const isSetPlayable = (exIdx: number, setIdx: number) => {
    // 0-indexed 组打卡判断
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
        contentContainerStyle={[styles.scrollContent, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 120 }]}
      >
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
            <Text style={[styles.sectionTitle, { color: textCol }]}>训练历史</Text>
            <View style={styles.timeline}>
              {trainingHistory.map((plan, idx) => (
                <HistoryCard key={idx} plan={plan} isDark={isDark} bg={cardBg} border={borderCol} text={textCol} sub={subTextCol} onPress={() => setSelectedPlan(plan)} />
              ))}
            </View>
          </View>
        )}
      </ScrollView>

      {/* History Detail Modal */}
      {selectedPlan && (
        <Modal animationType="slide" transparent visible={!!selectedPlan} onRequestClose={() => setSelectedPlan(null)}>
          <View style={styles.modalOverlay}>
            <View style={[styles.modalContent, { backgroundColor: cardBg, borderColor: borderCol }]}>
              <View style={styles.modalHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.modalTitle, { color: textCol }]}>{selectedPlan.title}</Text>
                  <Text style={{ fontSize: 12, color: subTextCol, marginTop: 4 }}>{formatDate(selectedPlan.completedAt)} · 已完成</Text>
                </View>
                <TouchableOpacity activeOpacity={0.7} style={[styles.closeBtn, { backgroundColor: isDark ? '#2C2C30' : '#E5E5EA' }]} onPress={() => setSelectedPlan(null)}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: textCol }}>✕</Text>
                </TouchableOpacity>
              </View>

              <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
                {selectedPlan.exercises.map((ex, exIdx) => {
                  const completedForEx = selectedPlan.completedKeys?.filter(k => k.startsWith(`${exIdx}-`)).length || 0;
                  const ratio = ex.sets > 0 ? Math.min(completedForEx / ex.sets, 1) : 0;
                  
                  return (
                    <View key={exIdx} style={{ marginBottom: 12, borderRadius: 12, overflow: 'hidden', backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', borderColor: borderCol, borderWidth: 0.5 }}>
                      <View style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: `${ratio * 100}%`, backgroundColor: 'rgba(52,199,89,0.15)' }} />
                      <View style={{ padding: 14, flexDirection: 'row', alignItems: 'center' }}>
                        <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)', justifyContent: 'center', alignItems: 'center', marginRight: 10 }}>
                          <Text style={{ fontSize: 11, fontWeight: '700', color: textCol }}>{exIdx + 1}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 15, fontWeight: '700', color: textCol, marginBottom: 4 }}>{ex.name}</Text>
                          <Text style={{ fontSize: 12, color: subTextCol }}>计划: {ex.sets} 组 × {ex.reps}{ex.weight ? ` · ${ex.weight}` : ''}</Text>
                        </View>
                        <Text style={{ fontSize: 14, fontWeight: '700', color: ratio === 1 ? '#34C759' : textCol }}>
                          {completedForEx}/{ex.sets}
                        </Text>
                      </View>
                    </View>
                  );
                })}
              </ScrollView>

              <TouchableOpacity activeOpacity={0.7} style={{ margin: 16, paddingVertical: 14, borderRadius: 14, backgroundColor: accentCol, alignItems: 'center' }} onPress={() => setSelectedPlan(null)}>
                <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 14 }}>返回</Text>
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
  // Timeline
  timeline: { gap: 0 },
  historyCard: { borderRadius: 12, borderWidth: 0.5, marginBottom: 10, overflow: 'hidden' },
  historyLeft: { position: 'absolute', left: 12, top: 0, bottom: 0, alignItems: 'center', paddingTop: 14 },
  historyDot: { width: 8, height: 8, borderRadius: 4 },
  historyLine: { width: 1.5, flex: 1, marginTop: 4 },
  historyContent: { paddingLeft: 30, padding: 12 },
  historyHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 },
  historyTitle: { fontSize: 14, fontWeight: '700', flex: 1 },
  historyBadge: { paddingHorizontal: 6, paddingVertical: 1.5, borderRadius: 5, marginLeft: 6 },
  historyBadgeText: { fontSize: 9, fontWeight: '700' },
  historyMeta: { fontSize: 10, marginBottom: 6 },
  historyExercises: { gap: 2 },
  historyExItem: { fontSize: 10 },
  // Modals
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { width: '100%', maxWidth: 480, height: '70%', borderRadius: 20, borderWidth: 0.5, overflow: 'hidden' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 0.5, borderBottomColor: '#2C2C2E' },
  modalTitle: { fontSize: 16, fontWeight: '800', letterSpacing: -0.4 },
  closeBtn: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
});
