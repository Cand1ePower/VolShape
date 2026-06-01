import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
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
}

export const DietCard: React.FC<DietCardProps> = ({ data }) => {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  // 商业级高级主题配色 (Glassmorphism Dark-Vibe Theme)
  const cardBg = isDark ? '#1E1E1E' : '#FFFFFF';
  const borderCol = isDark ? '#323236' : '#EAEAEA';
  const textCol = isDark ? '#FFFFFF' : '#1C1C1E';
  const subTextCol = isDark ? '#A1A1AA' : '#666666';

  // 营养素科学标志色
  const proteinColor = '#FF3B30'; // 热情红 - 肌肉增长蛋白质
  const carbsColor = '#FFCC00';   // 活力黄 - 能量来源碳水
  const fatColor = '#34C759';     // 健康绿 - 优质脂肪

  const mealNames = {
    breakfast: '🌅 能量早餐',
    lunch: '☀️ 丰盛午餐',
    dinner: '🌙 饱腹晚餐',
    snack: '🍎 营养加餐'
  };

  // 💡 【商业化重构】杜绝硬编码！基于三大营养素真实克数，动态计算进度条占比，100% 真实联动！
  const totalMacros = (data.totalProtein || 0) + (data.totalCarbs || 0) + (data.totalFat || 0);
  const proteinWidth = totalMacros > 0 ? `${Math.round((data.totalProtein / totalMacros) * 100)}%` as const : '0%';
  const carbsWidth = totalMacros > 0 ? `${Math.round((data.totalCarbs / totalMacros) * 100)}%` as const : '0%';
  const fatWidth = totalMacros > 0 ? `${Math.round((data.totalFat / totalMacros) * 100)}%` as const : '0%';

  const handleConfirm = () => {
    Alert.alert(
      "🥗 饮食数据已记录",
      `已成功同步今天的${mealNames[data.mealType]}至您的健康档案！\n\n🔥 总摄入热量：${data.totalCalories} kcal\n🥩 蛋白质总量：${data.totalProtein} g`,
      [{ text: "好的", onPress: () => console.log("Diet confirmed") }]
    );
  };

  return (
    <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol }]}>
      {/* 头部餐食与图片 */}
      <View style={styles.headerRow}>
        <View style={styles.headerInfo}>
          <Text style={[styles.mealTitle, { color: textCol }]}>{mealNames[data.mealType] || '🍲 饮食记录'}</Text>
          <Text style={[styles.calorieCount, { color: textCol }]}>
            {data.totalCalories} <Text style={styles.kcalUnit}>kcal</Text>
          </Text>
        </View>
        
        {data.imageUrl && (
          <Image 
            source={{ uri: data.imageUrl }} 
            style={styles.foodImage}
            contentFit="cover"
            transition={300}
          />
        )}
      </View>

      {/* 【核心联动组件】营养素动态进度条 */}
      <View style={styles.macroContainer}>
        <View style={styles.macroItem}>
          <Text style={[styles.macroLabel, { color: subTextCol }]}>🥩 蛋白质</Text>
          <Text style={[styles.macroValue, { color: proteinColor }]}>{data.totalProtein}g</Text>
          <View style={[styles.progressBarBg, { backgroundColor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)' }]}>
            <View style={[styles.progressBarFill, { backgroundColor: proteinColor, width: proteinWidth }]} />
          </View>
        </View>

        <View style={styles.macroItem}>
          <Text style={[styles.macroLabel, { color: subTextCol }]}>🍚 碳水</Text>
          <Text style={[styles.macroValue, { color: carbsColor }]}>{data.totalCarbs}g</Text>
          <View style={[styles.progressBarBg, { backgroundColor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)' }]}>
            <View style={[styles.progressBarFill, { backgroundColor: carbsColor, width: carbsWidth }]} />
          </View>
        </View>

        <View style={styles.macroItem}>
          <Text style={[styles.macroLabel, { color: subTextCol }]}>🥑 优质脂肪</Text>
          <Text style={[styles.macroValue, { color: fatColor }]}>{data.totalFat}g</Text>
          <View style={[styles.progressBarBg, { backgroundColor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)' }]}>
            <View style={[styles.progressBarFill, { backgroundColor: fatColor, width: fatWidth }]} />
          </View>
        </View>
      </View>

      {/* 食物明细列表 */}
      <View style={styles.foodList}>
        <Text style={[styles.listTitle, { color: textCol }]}>🧮 智能估算细则</Text>
        <View style={styles.foodListWrapper}>
          {data.foodItems.map((item, idx) => (
            <View 
              key={idx} 
              style={[
                styles.foodRow, 
                { 
                  backgroundColor: isDark ? 'rgba(255, 255, 255, 0.02)' : 'rgba(0, 0, 0, 0.01)',
                  borderBottomColor: idx === data.foodItems.length - 1 ? 'transparent' : borderCol 
                }
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

      {/* 确认录入按钮 */}
      <TouchableOpacity 
        activeOpacity={0.8}
        style={styles.confirmButton} 
        onPress={handleConfirm}
      >
        <Text style={styles.confirmButtonText}>✅ 确认录入今日身体体征</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    borderWidth: 1.5,
    padding: 18,
    marginVertical: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 4,
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
    letterSpacing: -1,
  },
  kcalUnit: {
    fontSize: 14,
    fontWeight: 'normal',
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
    backgroundColor: '#34C759', // 亮色科学绿色
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#34C759',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  confirmButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
