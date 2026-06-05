import React, { useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View, useColorScheme } from 'react-native';

export interface PortionConfirmItem {
  name: string;
  display_name: string;
  selected_weight_g: number;
  portion_options_g: number[];
  estimated_calories: number;
  estimated_protein: number;
  estimated_carbs: number;
  estimated_fat: number;
  confidence?: number;
  portion_basis?: string;
}

export interface PortionConfirmCardData {
  type: 'portion_confirm_card';
  mealType: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  prompt: string;
  portionNote?: string;
  items: PortionConfirmItem[];
}

interface PortionConfirmCardProps {
  data: PortionConfirmCardData;
  loading?: boolean;
  onConfirm: (items: PortionConfirmItem[]) => void;
}

const mealNames = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
  snack: '加餐',
};

export const PortionConfirmCard: React.FC<PortionConfirmCardProps> = ({ data, loading = false, onConfirm }) => {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const [selectedWeights, setSelectedWeights] = useState<Record<number, number>>(
    Object.fromEntries(data.items.map((item, index) => [index, item.selected_weight_g]))
  );

  const textCol = isDark ? '#FFFFFF' : '#111827';
  const subTextCol = isDark ? '#A1A1AA' : '#6B7280';
  const cardBg = isDark ? 'rgba(24, 24, 28, 0.82)' : 'rgba(255, 255, 255, 0.96)';
  const borderCol = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)';

  const confirmItems = useMemo(
    () =>
      data.items.map((item, index) => ({
        ...item,
        selected_weight_g: selectedWeights[index] || item.selected_weight_g,
      })),
    [data.items, selectedWeights]
  );

  return (
    <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol }]}>
      <Text style={[styles.title, { color: textCol }]}>确认这顿{mealNames[data.mealType] || '饮食'}的分量</Text>
      <Text style={[styles.subtitle, { color: subTextCol }]}>
        我已经先识别出主要食物了。你确认一下每样食物的大致重量，我再给出更可靠的营养估算。
      </Text>

      {data.portionNote ? (
        <Text style={[styles.note, { color: subTextCol }]}>识别备注：{data.portionNote}</Text>
      ) : null}

      <View style={styles.list}>
        {confirmItems.map((item, index) => (
          <View key={`${item.name}-${index}`} style={[styles.itemCard, { borderColor: borderCol }]}>
            <View style={styles.itemHeader}>
              <Text style={[styles.itemName, { color: textCol }]}>{item.display_name || item.name}</Text>
              <Text style={[styles.itemMeta, { color: subTextCol }]}>
                识别置信度 {Math.round((item.confidence || 0) * 100)}%
              </Text>
            </View>

            <View style={styles.optionRow}>
              {item.portion_options_g.map((weight) => {
                const active = selectedWeights[index] === weight;
                return (
                  <TouchableOpacity
                    key={`${item.name}-${weight}`}
                    style={[
                      styles.optionChip,
                      {
                        backgroundColor: active ? '#007AFF' : 'transparent',
                        borderColor: active ? '#007AFF' : borderCol,
                      },
                    ]}
                    onPress={() => setSelectedWeights((prev) => ({ ...prev, [index]: weight }))}
                    disabled={loading}
                  >
                    <Text style={[styles.optionText, { color: active ? '#FFFFFF' : textCol }]}>{weight}g</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.confirmButton, { opacity: loading ? 0.72 : 1 }]}
        onPress={() => onConfirm(confirmItems)}
        disabled={loading}
      >
        {loading ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Text style={styles.confirmText}>确认分量并生成营养分析</Text>}
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 20,
    borderWidth: 0.5,
    padding: 16,
    gap: 12,
  },
  title: {
    fontSize: 17,
    fontWeight: '800',
  },
  subtitle: {
    fontSize: 13,
    lineHeight: 20,
  },
  note: {
    fontSize: 12,
    lineHeight: 18,
  },
  list: {
    gap: 10,
  },
  itemCard: {
    borderWidth: 0.5,
    borderRadius: 14,
    padding: 12,
    gap: 10,
  },
  itemHeader: {
    gap: 4,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '700',
  },
  itemMeta: {
    fontSize: 11,
  },
  optionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  optionChip: {
    minWidth: 70,
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
  },
  optionText: {
    fontSize: 13,
    fontWeight: '700',
  },
  confirmButton: {
    marginTop: 4,
    backgroundColor: '#007AFF',
    borderRadius: 14,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  confirmText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '800',
  },
});
