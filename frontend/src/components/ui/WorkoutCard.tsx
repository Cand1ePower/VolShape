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
  notes?: string;
}

export interface WorkoutCardData {
  type: 'workout_card';
  title: string;
  targetMuscles: string[];
  exercises: Exercise[];
  disclaimer?: string;
}

interface WorkoutCardProps {
  data: WorkoutCardData;
}

export const WorkoutCard: React.FC<WorkoutCardProps> = ({ data }) => {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const { setActivePlan } = usePlan();

  const cardBg = isDark ? 'rgba(28, 28, 33, 0.65)' : 'rgba(255, 255, 255, 0.72)';
  const borderCol = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
  const textCol = isDark ? '#FFFFFF' : '#1C1C1E';
  const subTextCol = isDark ? '#8E8E93' : '#666666';
  const accentCol = '#007AFF';
  const accentBg = isDark ? 'rgba(0, 122, 255, 0.15)' : 'rgba(0, 122, 255, 0.08)';

  const handleApply = () => {
    setActivePlan({
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
        activeOpacity={0.8}
        style={[styles.applyButton, { backgroundColor: accentCol }]} 
        onPress={handleApply}
      >
        <Text style={styles.applyButtonText}>应用此计划并开始训练</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 24,
    borderWidth: 1,
    padding: 18,
    marginVertical: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.06,
    shadowRadius: 24,
    elevation: 2,
    alignSelf: 'stretch',
  },
  header: {
    marginBottom: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 10,
    letterSpacing: -0.5,
  },
  chipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 14,
  },
  chipText: {
    fontSize: 12,
    fontWeight: '700',
  },
  exerciseList: {
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 16,
  },
  exerciseItem: {
    padding: 14,
    borderBottomWidth: 1,
  },
  exerciseHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  numberBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  exerciseNumber: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  exerciseName: {
    flex: 1,
    fontSize: 15,
    fontWeight: '700',
  },
  volumeBadge: {
    backgroundColor: '#007AFF15',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  volumeText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#007AFF',
  },
  weightBadge: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255, 149, 0, 0.12)',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 6,
    marginBottom: 8,
  },
  weightText: {
    color: '#FF9500',
    fontSize: 11,
    fontWeight: '700',
  },
  notesContainer: {
    borderLeftWidth: 3,
    paddingLeft: 8,
    marginTop: 4,
  },
  exerciseNotes: {
    fontSize: 12,
    lineHeight: 18,
    fontStyle: 'italic',
  },
  disclaimerContainer: {
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
  },
  disclaimerText: {
    fontSize: 12,
    lineHeight: 18,
    fontWeight: '600',
  },
  applyButton: {
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  applyButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
