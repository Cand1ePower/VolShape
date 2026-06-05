import React from 'react';
import { Platform, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { useColorScheme } from 'react-native';

export interface FoodItem {
  name: string;
  weight_g: number;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

export interface DietCardData {
  type: 'diet_card';
  record_id?: string;
  confirmed?: boolean;
  mealType: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  foodItems: FoodItem[];
  totalCalories: number;
  totalProtein: number;
  totalCarbs: number;
  totalFat: number;
  imageUrl?: string;
}

interface DietCardProps {
  data: DietCardData;
  onConfirm?: () => void;
}

export const DietCard: React.FC<DietCardProps> = ({ data, onConfirm }) => {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  const cardBg = isDark ? 'rgba(28, 28, 33, 0.65)' : 'rgba(255, 255, 255, 0.72)';
  const borderCol = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
  const textCol = isDark ? '#FFFFFF' : '#1C1C1E';
  const subTextCol = isDark ? '#8E8E93' : '#666666';

  const proteinColor = '#FF5A4F';
  const carbsColor = '#FFD24A';
  const fatColor = '#66D16F';

  const mealNames = {
    breakfast: '营养早餐',
    lunch: '均衡午餐',
    dinner: '恢复晚餐',
    snack: '营养加餐',
  };

  const totalMacros = (data.totalProtein || 0) + (data.totalCarbs || 0) + (data.totalFat || 0);
  const proteinWidth = totalMacros > 0 ? `${Math.round((data.totalProtein / totalMacros) * 100)}%` as const : '0%';
  const carbsWidth = totalMacros > 0 ? `${Math.round((data.totalCarbs / totalMacros) * 100)}%` as const : '0%';
  const fatWidth = totalMacros > 0 ? `${Math.round((data.totalFat / totalMacros) * 100)}%` as const : '0%';

  const isConfirmed = Boolean(data.confirmed);

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: cardBg,
          borderColor: borderCol,
          ...Platform.select({
            web: { backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' } as any,
            default: {},
          }),
        },
      ]}
    >
      <View style={styles.headerRow}>
        <View style={styles.headerInfo}>
          <Text style={[styles.mealTitle, { color: textCol }]}>{mealNames[data.mealType] || '饮食记录'}</Text>
          <Text style={[styles.calorieCount, { color: textCol }]}>
            {data.totalCalories} <Text style={styles.kcalUnit}>kcal</Text>
          </Text>
        </View>

        {data.imageUrl ? (
          <Image source={{ uri: data.imageUrl }} style={styles.foodImage} contentFit="cover" transition={300} />
        ) : null}
      </View>

      <View style={styles.macroContainer}>
        <View style={styles.macroItem}>
          <Text style={[styles.macroLabel, { color: subTextCol }]}>蛋白质</Text>
          <Text style={[styles.macroValue, { color: proteinColor }]}>{data.totalProtein}g</Text>
          <View style={[styles.progressBarBg, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)' }]}>
            <View style={[styles.progressBarFill, { backgroundColor: proteinColor, width: proteinWidth }]} />
          </View>
        </View>

        <View style={styles.macroItem}>
          <Text style={[styles.macroLabel, { color: subTextCol }]}>碳水化合物</Text>
          <Text style={[styles.macroValue, { color: carbsColor }]}>{data.totalCarbs}g</Text>
          <View style={[styles.progressBarBg, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)' }]}>
            <View style={[styles.progressBarFill, { backgroundColor: carbsColor, width: carbsWidth }]} />
          </View>
        </View>

        <View style={styles.macroItem}>
          <Text style={[styles.macroLabel, { color: subTextCol }]}>优质脂肪</Text>
          <Text style={[styles.macroValue, { color: fatColor }]}>{data.totalFat}g</Text>
          <View style={[styles.progressBarBg, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)' }]}>
            <View style={[styles.progressBarFill, { backgroundColor: fatColor, width: fatWidth }]} />
          </View>
        </View>
      </View>

      <View style={styles.foodList}>
        <Text style={[styles.listTitle, { color: textCol }]}>智能估算细则</Text>
        <View style={styles.foodListWrapper}>
          {data.foodItems.map((item, idx) => (
            <View
              key={`${item.name}-${idx}`}
              style={[
                styles.foodRow,
                {
                  backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)',
                  borderBottomColor: idx === data.foodItems.length - 1 ? 'transparent' : borderCol,
                },
              ]}
            >
              <View style={styles.foodNameCol}>
                <Text style={[styles.foodName, { color: textCol }]}>{item.name}</Text>
                <Text style={[styles.foodWeight, { color: subTextCol }]}>{item.weight_g} 克</Text>
              </View>
              <View style={styles.foodMacroCol}>
                <Text style={[styles.foodCal, { color: textCol }]}>{item.calories} kcal</Text>
                <Text style={[styles.foodPcf, { color: subTextCol }]}>
                  蛋白:{item.protein} 碳水:{item.carbs} 脂肪:{item.fat}
                </Text>
              </View>
            </View>
          ))}
        </View>
      </View>

      <TouchableOpacity
        activeOpacity={isConfirmed ? 1 : 0.82}
        disabled={isConfirmed}
        style={[styles.confirmButton, isConfirmed ? styles.confirmButtonDone : null]}
        onPress={onConfirm}
      >
        <Text style={styles.confirmButtonText}>
          {isConfirmed ? '已同步到营养档案' : '确认记录到营养档案'}
        </Text>
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
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 18,
  },
  headerInfo: {
    flex: 1,
  },
  mealTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  calorieCount: {
    fontSize: 30,
    fontWeight: '900',
  },
  kcalUnit: {
    fontSize: 14,
    fontWeight: '400',
    color: '#8E8E93',
  },
  foodImage: {
    width: 76,
    height: 76,
    borderRadius: 14,
    marginLeft: 16,
  },
  macroContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 22,
    gap: 12,
  },
  macroItem: {
    flex: 1,
  },
  macroLabel: {
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 4,
  },
  macroValue: {
    fontSize: 15,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  progressBarBg: {
    height: 5,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  foodList: {
    marginBottom: 18,
  },
  listTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  foodListWrapper: {
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'transparent',
  },
  foodRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 12,
    borderBottomWidth: 0.5,
  },
  foodNameCol: {
    flex: 1,
  },
  foodName: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 4,
  },
  foodWeight: {
    fontSize: 11,
  },
  foodMacroCol: {
    alignItems: 'flex-end',
    flexShrink: 1,
    marginLeft: 10,
  },
  foodCal: {
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  foodPcf: {
    fontSize: 10,
    fontWeight: '600',
  },
  confirmButton: {
    backgroundColor: '#34C759',
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#34C759',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  confirmButtonDone: {
    backgroundColor: '#2C2C2E',
    shadowOpacity: 0,
  },
  confirmButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
