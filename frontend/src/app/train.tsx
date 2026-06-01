import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useColorScheme, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePlan, CompletedPlan } from '@/contexts/PlanContext';

const MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

function formatDate(d: Date): string {
  return `${MONTHS[d.getMonth()]}${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function HistoryCard({ plan, isDark, bg, border, text, sub }: { plan: CompletedPlan; isDark: boolean; bg: string; border: string; text: string; sub: string }) {
  const done = plan.completedSets >= plan.totalSets;
  return (
    <View style={[styles.historyCard, { backgroundColor: bg, borderColor: border }]}>
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
          {plan.exercises.slice(0, 4).map((ex, i) => (
            <Text key={i} style={[styles.historyExItem, { color: sub }]}>
              {ex.name} {ex.sets}×{ex.reps}
            </Text>
          ))}
          {plan.exercises.length > 4 && (
            <Text style={[styles.historyExItem, { color: sub }]}>+{plan.exercises.length - 4} 更多</Text>
          )}
        </View>
      </View>
    </View>
  );
}

export default function TrainScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { activePlan, completedExercises, toggleComplete, completePlan, resetPlan, trainingHistory } = usePlan();

  const isSetPlayable = (exIdx: number, setIdx: number) => {
    // 0-indexed 组打卡判断
    if (setIdx === 0) {
      // 第一组，永远可以点击。如果要取消，下一组必须为未打勾状态
      if (completedExercises.has(`${exIdx}-0`)) {
        return !completedExercises.has(`${exIdx}-1`);
      }
      return true;
    }
    
    const prevKey = `${exIdx}-${setIdx - 1}`;
    const currentKey = `${exIdx}-${setIdx}`;
    const nextKey = `${exIdx}-${setIdx + 1}`;
    
    if (completedExercises.has(currentKey)) {
      // 已经完成了。如果需要取消打勾，下一组必须是未完成状态
      return !completedExercises.has(nextKey);
    } else {
      // 还没完成。如果需要点击打勾，前一组必须是已完成状态
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
                          opacity: playable ? 1 : 0.35, // 未解锁灰度
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
                <HistoryCard key={idx} plan={plan} isDark={isDark} bg={cardBg} border={borderCol} text={textCol} sub={subTextCol} />
              ))}
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { paddingHorizontal: 20 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: '800', marginBottom: 14, letterSpacing: -0.5 },
  header: { marginBottom: 20 },
  title: { fontSize: 22, fontWeight: '800', letterSpacing: -0.8, marginBottom: 10 },
  disclaimerBox: { borderRadius: 10, padding: 12, marginBottom: 14 },
  disclaimerText: { fontSize: 12, fontWeight: '600', lineHeight: 18 },
  progressBar: { height: 8, borderRadius: 4, marginBottom: 8, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 4 },
  progressText: { fontSize: 13, fontWeight: '600' },
  exerciseCard: { borderRadius: 16, borderWidth: 0.5, padding: 16, marginBottom: 12 },
  exerciseHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8 },
  exNum: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  exNumText: { fontSize: 13, fontWeight: '700' },
  exInfo: { flex: 1 },
  exName: { fontSize: 16, fontWeight: '700', marginBottom: 2 },
  exMeta: { fontSize: 13 },
  exNotes: { fontSize: 12, fontStyle: 'italic', marginBottom: 12, paddingLeft: 40 },
  setRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingLeft: 40 },
  setChip: { borderWidth: 1, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 14 },
  setChipText: { fontSize: 13, fontWeight: '600' },
  actionRow: { flexDirection: 'row', gap: 10, marginTop: 8 },
  finishBtn: { flex: 1, borderRadius: 16, paddingVertical: 15, alignItems: 'center' },
  finishBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
  cancelBtn: { borderRadius: 16, paddingVertical: 15, paddingHorizontal: 20, alignItems: 'center', borderWidth: 1 },
  cancelBtnText: { fontSize: 14, fontWeight: '600' },
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 20, fontWeight: '700', marginBottom: 8 },
  emptySub: { fontSize: 14, textAlign: 'center', lineHeight: 22 },
  // Timeline
  timeline: { gap: 0 },
  historyCard: { borderRadius: 14, borderWidth: 0.5, marginBottom: 12, overflow: 'hidden' },
  historyLeft: { position: 'absolute', left: 14, top: 0, bottom: 0, alignItems: 'center', paddingTop: 18 },
  historyDot: { width: 10, height: 10, borderRadius: 5 },
  historyLine: { width: 2, flex: 1, marginTop: 4 },
  historyContent: { paddingLeft: 36, padding: 16 },
  historyHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  historyTitle: { fontSize: 15, fontWeight: '700', flex: 1 },
  historyBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, marginLeft: 8 },
  historyBadgeText: { fontSize: 10, fontWeight: '700' },
  historyMeta: { fontSize: 11, marginBottom: 8 },
  historyExercises: { gap: 2 },
  historyExItem: { fontSize: 11 },
});
