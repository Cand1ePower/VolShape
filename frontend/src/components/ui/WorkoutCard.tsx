import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native';
import { useColorScheme } from 'react-native';
import { usePlan } from '@/contexts/PlanContext';
import { router } from 'expo-router';

export interface Exercise {
  name: string;
  sets: number;
  reps: string;
  weight?: string;
  rest_seconds?: number;
  notes?: string;
}

export interface WorkoutCardData {
  type: 'workout_card';
  title: string;
  targetMuscles: string[];
  exercises: Exercise[];
  disclaimer?: string;
  plan_id?: string; // 🌟 后端物理主键 plan_id
}

interface WorkoutCardProps {
  data: WorkoutCardData;
}

export const WorkoutCard: React.FC<WorkoutCardProps> = ({ data }) => {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const { planStatusMap, applyWorkoutOnBackend } = usePlan();

  const cardBg = isDark ? 'rgba(28, 28, 33, 0.65)' : 'rgba(255, 255, 255, 0.72)';
  const borderCol = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
  const textCol = isDark ? '#FFFFFF' : '#1C1C1E';
  const subTextCol = isDark ? '#8E8E93' : '#666666';
  const accentCol = '#007AFF';
  const accentBg = isDark ? 'rgba(0, 122, 255, 0.15)' : 'rgba(0, 122, 255, 0.08)';

  const planId = data.plan_id;
  const status = planId ? (planStatusMap[planId] || 'active') : 'active';

  const handleApply = async () => {
    if (!planId) return;
    await applyWorkoutOnBackend(planId, {
      title: data.title || '今日训练计划',
      exercises: data.exercises.map(e => ({
        name: e.name,
        sets: e.sets,
        reps: e.reps,
        weight: e.weight || '',
        notes: e.notes || '',
      })),
      disclaimer: data.disclaimer,
      createdAt: new Date(),
    });
    router.navigate('/train');
  };

  return (
    <View style={[
      styles.card, 
      { 
        backgroundColor: cardBg, 
        borderColor: borderCol,
        ...Platform.select({
          web: { backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } as any,
          default: {}
        })
      }
    ]}>
      {/* 头部：徽章与计划标题 */}
      <View style={styles.header}>
        <Text style={[styles.title, { color: textCol }]}>{data.title}</Text>
        <View style={styles.chipContainer}>
          {data.targetMuscles.map((muscle, idx) => (
            <View key={idx} style={[styles.chip, { backgroundColor: accentBg }]}>
              <Text style={[styles.chipText, { color: accentCol }]}>{muscle}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* 精致卡牌化动作列表 */}
      <View style={styles.exerciseList}>
        {data.exercises.map((item, idx) => (
          <View 
            key={idx} 
            style={[
              styles.exerciseItem, 
              { 
                backgroundColor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.015)',
                borderColor: borderCol,
                borderBottomWidth: idx === data.exercises.length - 1 ? 0 : 1
              }
            ]}
          >
            <View style={styles.exerciseHeader}>
              <View style={[styles.numberBadge, { backgroundColor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)' }]}>
                <Text style={[styles.exerciseNumber, { color: textCol }]}>{idx + 1}</Text>
              </View>
              <Text style={[styles.exerciseName, { color: textCol }]}>{item.name}</Text>
              <View style={styles.volumeBadge}>
                <Text style={styles.volumeText}>
                  {item.sets} 组 × {item.reps}
                </Text>
              </View>
            </View>
            
            {item.weight && (
              <View style={styles.weightBadge}>
                <Text style={styles.weightText}>推荐负荷: {item.weight}</Text>
              </View>
            )}

            {item.rest_seconds && (
              <View style={styles.restBadge}>
                <Text style={styles.restText}>⏱ 组间休息 {item.rest_seconds}s</Text>
              </View>
            )}

            {item.notes && (
              <View style={[styles.notesContainer, { borderLeftColor: accentCol }]}>
                <Text style={[styles.exerciseNotes, { color: subTextCol }]}>
                  {item.notes}
                </Text>
              </View>
            )}
          </View>
        ))}
      </View>

      {/* 科学安全免责声明 */}
      {data.disclaimer && (
        <View style={[styles.disclaimerContainer, { backgroundColor: isDark ? 'rgba(255, 149, 0, 0.1)' : 'rgba(255, 149, 0, 0.05)' }]}>
          <Text style={[styles.disclaimerText, { color: '#FF9500' }]}>
            安全提示：{data.disclaimer}
          </Text>
        </View>
      )}

      {/* 交互回弹效果按钮 */}
      <TouchableOpacity 
        activeOpacity={status === 'active' ? 0.8 : 1}
        disabled={status !== 'active'}
        style={[
          styles.applyButton, 
          { 
            backgroundColor: status === 'active' 
              ? accentCol 
              : status === 'training'
                ? (isDark ? 'rgba(0, 122, 255, 0.15)' : 'rgba(0, 122, 255, 0.08)')
                : (isDark ? 'rgba(52, 199, 89, 0.15)' : 'rgba(52, 199, 89, 0.08)'),
            borderColor: status === 'active'
              ? 'transparent'
              : status === 'training'
                ? '#007AFF50'
                : '#34C75950',
            borderWidth: status === 'active' ? 0 : 1,
            shadowOpacity: status === 'active' ? 0.3 : 0
          }
        ]} 
        onPress={handleApply}
      >
        <Text style={[
          styles.applyButtonText, 
          { 
            color: status === 'active' 
              ? '#FFFFFF' 
              : status === 'training'
                ? '#007AFF'
                : '#34C759'
          }
        ]}>
          {status === 'active' 
            ? '应用此计划并开始训练' 
            : status === 'training'
              ? '应用中...'
              : '已完成'}
        </Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    borderWidth: 0.5,
    padding: 16,
    marginVertical: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 1,
    alignSelf: 'stretch',
  },
  header: {
    marginBottom: 14,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
    letterSpacing: -0.3,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  chipText: {
    fontSize: 11,
    fontWeight: '700',
  },
  exerciseList: {
    borderRadius: 10,
    overflow: 'hidden',
    marginBottom: 14,
  },
  exerciseItem: {
    padding: 12,
    borderBottomWidth: 0.5,
  },
  exerciseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  numberBadge: {
    width: 20,
    height: 20,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  exerciseNumber: {
    fontSize: 11,
    fontWeight: 'bold',
  },
  exerciseName: {
    flex: 1,
    fontSize: 14,
    fontWeight: '700',
  },
  volumeBadge: {
    backgroundColor: '#007AFF15',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  volumeText: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#007AFF',
  },
  weightBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255, 149, 0, 0.12)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 5,
    marginBottom: 6,
  },
  weightText: {
    color: '#FF9500',
    fontSize: 10,
    fontWeight: '700',
  },
  restBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(88, 86, 214, 0.10)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 5,
    marginBottom: 6,
  },
  restText: {
    color: '#5856D6',
    fontSize: 10,
    fontWeight: '700',
  },
  notesContainer: {
    borderLeftWidth: 2,
    paddingLeft: 6,
    marginTop: 4,
  },
  exerciseNotes: {
    fontSize: 11,
    lineHeight: 16,
    fontStyle: 'italic',
  },
  disclaimerContainer: {
    borderRadius: 8,
    padding: 10,
    marginBottom: 14,
  },
  disclaimerText: {
    fontSize: 11,
    lineHeight: 16,
    fontWeight: '600',
  },
  applyButton: {
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
  },
  applyButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: 'bold',
  },
});
