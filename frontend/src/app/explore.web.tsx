import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollView, View, Text, StyleSheet, useColorScheme, Platform,
  TouchableOpacity, useWindowDimensions, Modal, ActivityIndicator, TextInput,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { useAuth } from '@/contexts/AuthContext';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { getBackendBaseUrl } from '@/services/api';

const PLAN_CATALOG = [
  {
    id: 'free',
    tier: 'free',
    title: 'Free',
    price: '¥0',
    subtitle: '日常记录和轻量问答',
    dailyMessages: 10,
    monthlyQuota: '5 万',
    features: ['快速模式', '训练表生成'],
  },
  {
    id: 'trial_pro',
    tier: 'pro',
    title: 'Pro Trial',
    price: '7 天免费',
    subtitle: '每个账号限领一次',
    dailyMessages: 100,
    monthlyQuota: '试用额度',
    features: ['专家模式', '训练表生成', '完整记忆读取'],
  },
  {
    id: 'monthly_vip',
    tier: 'pro',
    title: 'Pro',
    price: '¥29/月',
    subtitle: '更高频的训练与饮食规划',
    dailyMessages: 100,
    monthlyQuota: '100 万',
    features: ['快速模式', '专家模式', '训练表生成'],
  },
  {
    id: 'annual_vip',
    tier: 'premium',
    title: 'Premium',
    price: '¥199/年',
    subtitle: '高频使用和长期追踪',
    dailyMessages: 500,
    monthlyQuota: '500 万',
    features: ['快速模式', '专家模式', '训练表生成', '周报'],
  },
] as const;

const tierLabel = (tier?: string | null) => {
  if (tier === 'premium') return 'Premium';
  if (tier === 'pro') return 'Pro';
  return 'Free';
};

const mealTypeLabel = (mealType?: string | null) => {
  if (mealType === 'breakfast') return '早餐';
  if (mealType === 'lunch') return '午餐';
  if (mealType === 'dinner') return '晚餐';
  if (mealType === 'snack') return '加餐';
  return '未分类';
};

export default function ExploreScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const safeAreaInsets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { userId, user, quota, isLoggedIn, login, register, logout, refreshMe, getValidToken } = useAuth();

  const insets = { ...safeAreaInsets, bottom: safeAreaInsets.bottom + BottomTabInset + Spacing.three };
  const isSmallScreen = width < 375;
  const [isWebMounted, setIsWebMounted] = useState(Platform.OS !== 'web');
  const isWeb = Platform.OS === 'web';
  const isDesktopWeb = isWebMounted && isWeb && width >= 1100;
  const dynamicPadding = isSmallScreen ? 14 : 18;
  const contentMaxWidth = isDesktopWeb ? 1040 : MaxContentWidth;

  const bgCol = isDark ? '#000000' : '#F2F2F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFFFFF';
  const borderCol = isDark ? '#2C2C2E' : '#E5E5EA';
  const textCol = isDark ? '#FFFFFF' : '#000000';
  const subTextCol = isDark ? '#AEAEB2' : '#8E8E93';

  // Login modal
  const [loginModalVisible, setLoginModalVisible] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authUsername, setAuthUsername] = useState('');
  const [authError, setAuthError] = useState('');
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Memory viewer modal
  const [memoryModalVisible, setMemoryModalVisible] = useState(false);
  const [memoryData, setMemoryData] = useState<any>(null);
  const [mem0Data, setMem0Data] = useState<any>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [plansVisible, setPlansVisible] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState('');
  const [expandedEventIndex, setExpandedEventIndex] = useState<number | null>(null);

  const displayValue = (value: any) => {
    if (!isLoggedIn) return '--';
    if (value === null || value === undefined || value === '') return '--';
    return String(value);
  };

  const goalLabel = (goal?: string | null) => {
    if (!isLoggedIn || !goal) return '--';
    if (goal === 'cut' || goal === 'fat_loss') return '减脂';
    if (goal === 'bulk' || goal === 'muscle_gain') return '增肌';
    if (goal === 'maintain') return '维持';
    if (goal === 'strength') return '力量';
    return goal;
  };

  const nutritionSummary = memoryData?.nutrition_summary || null;
  const latestNutrition = nutritionSummary?.latest_record || null;

  const formatMacroValue = (value: any, unit = '') => {
    if (!isLoggedIn) return '--';
    if (value === null || value === undefined || value === '') return '--';
    const numeric = typeof value === 'number' ? value : Number(value);
    if (Number.isNaN(numeric)) return '--';
    return `${numeric}${unit}`;
  };

  const loadProfileSnapshot = useCallback(async () => {
    try {
      const baseUrl = getBackendBaseUrl();
      const validToken = await getValidToken();
      if (!validToken) throw new Error('auth required');
      const response = await fetch(`${baseUrl}/api/chat/profile`, { headers: { Authorization: `Bearer ${validToken}`, Connection: 'close' } });
      const data = await response.json();
      setMemoryData(data);

      const mem0Resp = await fetch(`${baseUrl}/api/chat/mem0`, { headers: { Authorization: `Bearer ${validToken}`, Connection: 'close' } });
      const mem0Json = await mem0Resp.json();
      setMem0Data(mem0Json.memories || []);
    } catch (err) {
      console.log('Background fetching profile failed:', err);
    }
  }, [getValidToken]);

  const startCheckout = async (planId: string) => {
    const validToken = await getValidToken();
    if (!isLoggedIn || !validToken) {
      setPlansVisible(false);
      setLoginModalVisible(true);
      return;
    }
    setCheckoutError('');
    setCheckoutLoading(planId);
    try {
      const baseUrl = getBackendBaseUrl();
      const resp = await fetch(`${baseUrl}/api/payment/checkout?plan_id=${encodeURIComponent(planId)}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${validToken}`, Connection: 'close' },
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.message || '无法切换套餐');
      await refreshMe();
      setPlansVisible(false);
    } catch (e: any) {
      setCheckoutError(e?.message || '套餐切换暂时不可用');
    } finally {
      setCheckoutLoading(null);
    }
  };

  const fetchMemory = async () => {
    setMemoryLoading(true);
    setMemoryModalVisible(true);
    try {
      await loadProfileSnapshot();
    } catch (err) {
      console.error('Failed to fetch memory:', err);
    } finally {
      setMemoryLoading(false);
    }
  };

  const submitAuth = async () => {
    setAuthError('');
    setAuthSubmitting(true);
    try {
      if (authMode === 'login') {
        await login(authEmail, authPassword);
      } else {
        await register(authEmail, authPassword, authUsername || undefined);
      }
      setLoginModalVisible(false);
      setAuthPassword('');
      setAuthUsername('');
    } catch (e: any) {
      setAuthError(e?.message || '认证失败');
    } finally {
      setAuthSubmitting(false);
    }
  };

  // Automatically fetch metrics and profile in background when logged in
  useEffect(() => {
    if (Platform.OS === 'web') {
      setIsWebMounted(true);
    }
  }, []);

  useEffect(() => {
    if (isLoggedIn) {
      loadProfileSnapshot();
    } else {
      setMemoryData(null);
    }
  }, [isLoggedIn, loadProfileSnapshot]);

  useFocusEffect(
    useCallback(() => {
      if (isLoggedIn) {
        loadProfileSnapshot();
      }
    }, [isLoggedIn, loadProfileSnapshot])
  );

  return (
    <ScrollView style={{ backgroundColor: bgCol }} contentInset={insets} contentContainerStyle={[styles.scrollContent, {
      paddingTop: Platform.OS === 'android' ? insets.top + Spacing.two : Spacing.four,
      paddingBottom: insets.bottom,
      paddingHorizontal: isDesktopWeb ? 28 : Spacing.four,
    }]}>
      <View style={[styles.container, { maxWidth: contentMaxWidth }]}>
        <View style={styles.header}>
          <Text style={[styles.headerTitle, { color: textCol }]}>我的</Text>
          <Text style={[styles.headerSubtitle, { color: subTextCol }]}>账号 · 记忆 · 数据</Text>
        </View>

        {/* Account Card */}
        <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol, padding: dynamicPadding }]}>
          <Text style={[styles.cardTitle, { color: textCol }]}>账号与安全</Text>
          <View style={styles.accountRow}>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={[styles.acId, { color: textCol }]} numberOfLines={1}>
                  {isLoggedIn ? (user?.email || userId) : '未登录'}
                </Text>
                {isLoggedIn && (
                  <View style={[styles.statusBadge, { backgroundColor: quota?.tier === 'premium' ? 'rgba(255,149,0,0.15)' : quota?.tier === 'pro' ? 'rgba(88,86,214,0.14)' : 'rgba(0,122,255,0.1)' }]}>
                    <Text style={[styles.statusBadgeText, { color: quota?.tier === 'premium' ? '#FF9500' : quota?.tier === 'pro' ? '#5856D6' : '#007AFF' }]}>
                      {tierLabel(quota?.tier)}
                    </Text>
                  </View>
                )}
              </View>
            </View>
            {isLoggedIn ? (
              <View style={styles.accountActions}>
                <TouchableOpacity activeOpacity={0.7} style={styles.upgradeBtn} onPress={() => setPlansVisible(true)}>
                  <Text style={styles.upgradeBtnText}>升级</Text>
                </TouchableOpacity>
                <TouchableOpacity activeOpacity={0.7} style={styles.logoutBtn} onPress={() => { logout(); setMemoryData(null); }}>
                  <Text style={styles.logoutBtnText}>退出</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity activeOpacity={0.7} style={styles.loginBtn} onPress={() => setLoginModalVisible(true)}>
                <Text style={styles.loginBtnText}>登录</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Memory Card */}
        <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol, padding: dynamicPadding }]}>
          <View style={styles.memHeaderRow}>
            <Text style={[styles.cardTitle, { color: textCol }]}>AI 记忆管理</Text>
            <TouchableOpacity activeOpacity={0.7} style={styles.viewMemBtn} onPress={fetchMemory}>
              <Text style={styles.viewMemBtnText}>查看完整记忆</Text>
            </TouchableOpacity>
          </View>
          <Text style={[styles.memDesc, { color: subTextCol }]}>
            系统自动从你的对话中提取身体数据、训练能力、睡眠饮食等信息。点击查看 AI 记录的所有内容。
          </Text>
          {isLoggedIn && quota && (
            <TouchableOpacity activeOpacity={0.7} style={[styles.viewMemBtn, { alignSelf: 'flex-start', marginTop: 10 }]} onPress={refreshMe}>
              <Text style={styles.viewMemBtnText}>
                今日剩余 {quota.daily_messages_remaining}/{quota.daily_messages} · 本月剩余 {quota.monthly_quota_remaining}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Plan and Quota */}
        <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol, padding: dynamicPadding }]}>
          <View style={styles.memHeaderRow}>
            <View>
              <Text style={[styles.cardTitle, { color: textCol }]}>套餐与额度</Text>
              <Text style={[styles.planSubtitle, { color: subTextCol }]}>
                当前等级：{isLoggedIn ? tierLabel(quota?.tier) : '--'}
              </Text>
            </View>
            <TouchableOpacity activeOpacity={0.7} style={styles.viewMemBtn} onPress={() => setPlansVisible(true)}>
              <Text style={styles.viewMemBtnText}>{isLoggedIn ? '查看方案' : '登录查看'}</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quotaGrid}>
            <View style={styles.quotaItem}>
              <Text style={styles.statLabel}>快速模式</Text>
              <Text style={[styles.quotaVal, { color: textCol }]}>
                {isLoggedIn && quota ? `${quota.daily_messages_remaining}/${quota.daily_messages}` : '--'}
              </Text>
            </View>
            <View style={styles.quotaItem}>
              <Text style={styles.statLabel}>专家模式</Text>
              <Text style={[styles.quotaVal, { color: textCol }]}>
                {isLoggedIn && quota?.features?.detailed ? '可用' : isLoggedIn ? '升级解锁' : '--'}
              </Text>
            </View>
            <View style={styles.quotaItem}>
              <Text style={styles.statLabel}>训练表</Text>
              <Text style={[styles.quotaVal, { color: textCol }]}>
                {isLoggedIn && quota?.features?.training_sheet ? '可用' : isLoggedIn ? '不可用' : '--'}
              </Text>
            </View>
            <View style={styles.quotaItem}>
              <Text style={styles.statLabel}>本月模型额度</Text>
              <Text style={[styles.quotaVal, { color: textCol }]}>
                {isLoggedIn && quota ? `${quota.monthly_quota_remaining}/${quota.monthly_quota_units}` : '--'}
              </Text>
            </View>
          </View>
        </View>

        {/* Quick Stats */}
        <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol, padding: dynamicPadding }]}>
          <Text style={[styles.cardTitle, { color: textCol }]}>健康仪表盘</Text>
          <View style={styles.statGrid}>
            {[
              { 
                label: '身高', 
                val: displayValue(memoryData?.profile?.height_cm), 
                unit: isLoggedIn && memoryData?.profile?.height_cm ? 'cm' : '' 
              }, 
              { 
                label: '体重', 
                val: displayValue(memoryData?.profile?.metrics?.weight?.value), 
                unit: isLoggedIn && memoryData?.profile?.metrics?.weight?.value ? 'kg' : '' 
              }, 
              { 
                label: '体脂', 
                val: displayValue(memoryData?.profile?.metrics?.body_fat?.value), 
                unit: isLoggedIn && memoryData?.profile?.metrics?.body_fat?.value ? '%' : '' 
              }, 
              { 
                label: '目标', 
                val: goalLabel(memoryData?.profile?.goal), 
                unit: '' 
              }
            ].map((s, i) => (
              <View key={i} style={styles.statItem}>
                <Text style={styles.statLabel}>{s.label}</Text>
                <Text style={[styles.statVal, { color: textCol }]}>{s.val}<Text style={styles.statUnit}> {s.unit}</Text></Text>
              </View>
            ))}
          </View>
        </View>

        <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol, padding: dynamicPadding }]}>
          <View style={styles.memHeaderRow}>
            <View>
              <Text style={[styles.cardTitle, { color: textCol }]}>营养记录</Text>
              <Text style={[styles.planSubtitle, { color: subTextCol }]}>
                对话中的饮食卡片会自动同步到这里并持久化保存
              </Text>
            </View>
            {isLoggedIn && (
              <TouchableOpacity activeOpacity={0.7} style={styles.viewMemBtn} onPress={loadProfileSnapshot}>
                <Text style={styles.viewMemBtnText}>刷新营养数据</Text>
              </TouchableOpacity>
            )}
          </View>

          <View style={styles.statGrid}>
            {[
              { label: '今日热量', val: formatMacroValue(nutritionSummary?.today?.calories, ' kcal') },
              { label: '今日蛋白', val: formatMacroValue(nutritionSummary?.today?.protein, ' g') },
              { label: '7天日均热量', val: formatMacroValue(nutritionSummary?.last7days?.avg_calories, ' kcal') },
              { label: '7天记录餐次', val: formatMacroValue(nutritionSummary?.last7days?.meals_count, ' 次') },
            ].map((item, index) => (
              <View key={index} style={styles.statItem}>
                <Text style={styles.statLabel}>{item.label}</Text>
                <Text style={[styles.statVal, { color: textCol }]}>{item.val}</Text>
              </View>
            ))}
          </View>

          <View style={[styles.nutritionDetailCard, { backgroundColor: isDark ? 'rgba(52,199,89,0.08)' : 'rgba(52,199,89,0.06)' }]}>
            <View style={styles.nutritionDetailHeader}>
              <Text style={[styles.nutritionDetailTitle, { color: textCol }]}>最近一餐</Text>
              <Text style={[styles.nutritionMealType, { color: subTextCol }]}>
                {isLoggedIn && latestNutrition ? mealTypeLabel(latestNutrition.meal_type) : '--'}
              </Text>
            </View>
            <Text style={[styles.nutritionFoods, { color: subTextCol }]}>
              {isLoggedIn && latestNutrition?.food_items?.length
                ? latestNutrition.food_items.map((item: any) => item.name).join('、')
                : '暂无饮食记录'}
            </Text>
            <View style={styles.nutritionMacroRow}>
              <View style={styles.nutritionMacroItem}>
                <Text style={styles.statLabel}>热量</Text>
                <Text style={[styles.nutritionMacroValue, { color: textCol }]}>
                  {formatMacroValue(latestNutrition?.total_calories, ' kcal')}
                </Text>
              </View>
              <View style={styles.nutritionMacroItem}>
                <Text style={styles.statLabel}>蛋白质</Text>
                <Text style={[styles.nutritionMacroValue, { color: textCol }]}>
                  {formatMacroValue(latestNutrition?.total_protein, ' g')}
                </Text>
              </View>
              <View style={styles.nutritionMacroItem}>
                <Text style={styles.statLabel}>碳水</Text>
                <Text style={[styles.nutritionMacroValue, { color: textCol }]}>
                  {formatMacroValue(latestNutrition?.total_carbs, ' g')}
                </Text>
              </View>
              <View style={styles.nutritionMacroItem}>
                <Text style={styles.statLabel}>脂肪</Text>
                <Text style={[styles.nutritionMacroValue, { color: textCol }]}>
                  {formatMacroValue(latestNutrition?.total_fat, ' g')}
                </Text>
              </View>
            </View>
          </View>
        </View>

        <View style={{ height: Spacing.four }} />
      </View>

      {/* Login Modal */}
      <Modal animationType="slide" transparent visible={loginModalVisible} onRequestClose={() => setLoginModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.loginModal, { backgroundColor: cardBg, borderColor: borderCol }]}>
            <Text style={[styles.loginTitle, { color: textCol }]}>{authMode === 'login' ? '登录' : '创建账号'}</Text>
            <Text style={[styles.loginSub, { color: subTextCol }]}>使用 VolShape 账号同步训练、记忆和模型额度</Text>
            <View style={styles.authSwitch}>
              <TouchableOpacity activeOpacity={0.7} style={[styles.authSwitchBtn, authMode === 'login' && styles.authSwitchBtnActive]} onPress={() => setAuthMode('login')}>
                <Text style={[styles.authSwitchText, { color: authMode === 'login' ? '#FFFFFF' : subTextCol }]}>登录</Text>
              </TouchableOpacity>
              <TouchableOpacity activeOpacity={0.7} style={[styles.authSwitchBtn, authMode === 'register' && styles.authSwitchBtnActive]} onPress={() => setAuthMode('register')}>
                <Text style={[styles.authSwitchText, { color: authMode === 'register' ? '#FFFFFF' : subTextCol }]}>注册</Text>
              </TouchableOpacity>
            </View>
            {authMode === 'register' && (
              <TextInput style={[styles.loginInput, { color: textCol, borderColor: borderCol, backgroundColor: isDark ? '#0A0A0C' : '#F5F5F7' }]}
                value={authUsername} onChangeText={setAuthUsername} placeholder="昵称（可选）" placeholderTextColor={subTextCol} autoCapitalize="none" />
            )}
            <TextInput style={[styles.loginInput, { color: textCol, borderColor: borderCol, backgroundColor: isDark ? '#0A0A0C' : '#F5F5F7' }]}
              value={authEmail} onChangeText={setAuthEmail} placeholder="邮箱" placeholderTextColor={subTextCol} autoCapitalize="none" keyboardType="email-address" />
            <TextInput style={[styles.loginInput, { color: textCol, borderColor: borderCol, backgroundColor: isDark ? '#0A0A0C' : '#F5F5F7' }]}
              value={authPassword} onChangeText={setAuthPassword} placeholder="密码（至少 8 位）" placeholderTextColor={subTextCol} secureTextEntry />
            {!!authError && <Text style={{ color: '#FF3B30', fontSize: 12, marginBottom: 12, textAlign: 'center' }}>{authError}</Text>}
            <TouchableOpacity activeOpacity={0.7} style={[styles.loginConfirmBtn, { opacity: authSubmitting ? 0.7 : 1 }]} disabled={authSubmitting}
              onPress={submitAuth}>
              <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 15 }}>{authSubmitting ? '处理中...' : authMode === 'login' ? '确认登录' : '创建并登录'}</Text>
            </TouchableOpacity>
            <TouchableOpacity activeOpacity={0.7} onPress={() => setLoginModalVisible(false)} style={{ alignItems: 'center', paddingVertical: 8 }}>
              <Text style={{ color: '#007AFF', fontSize: 14 }}>取消</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Subscription Modal */}
      <Modal animationType="slide" transparent visible={plansVisible} onRequestClose={() => setPlansVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.plansModal, { backgroundColor: cardBg, borderColor: borderCol }]}>
            <View style={styles.memModalHeader}>
              <View>
                <Text style={[styles.cardTitle, { color: textCol }]}>选择套餐</Text>
                <Text style={[styles.planSubtitle, { color: subTextCol }]}>解锁更高额度、专家模式和长期追踪</Text>
              </View>
              <TouchableOpacity activeOpacity={0.7} style={[styles.closeCircle, { backgroundColor: isDark ? '#2C2C30' : '#E5E5EA' }]}
                onPress={() => setPlansVisible(false)}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: textCol }}>×</Text>
              </TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={styles.planList}>
              {PLAN_CATALOG.map((plan) => {
                const isCurrent = isLoggedIn && (plan.tier || 'free') === (quota?.tier || 'free');
                return (
                  <View key={plan.id} style={[styles.planCard, { borderColor: isCurrent ? '#007AFF' : borderCol, backgroundColor: isDark ? '#0A0A0C' : '#F8F8FA' }]}>
                    <View style={styles.planTopRow}>
                      <View>
                        <Text style={[styles.planTitle, { color: textCol }]}>{plan.title}</Text>
                        <Text style={[styles.planSubtitle, { color: subTextCol }]}>{plan.subtitle}</Text>
                      </View>
                      <Text style={[styles.planPrice, { color: textCol }]}>{plan.price}</Text>
                    </View>
                    <View style={styles.planMetaRow}>
                      <Text style={[styles.planMeta, { color: subTextCol }]}>每日 {plan.dailyMessages} 次</Text>
                      <Text style={[styles.planMeta, { color: subTextCol }]}>每月 {plan.monthlyQuota} 额度</Text>
                    </View>
                    <View style={styles.featureWrap}>
                      {plan.features.map((feature) => (
                        <View key={feature} style={styles.featurePill}>
                          <Text style={styles.featurePillText}>{feature}</Text>
                        </View>
                      ))}
                    </View>
                    <TouchableOpacity
                      activeOpacity={0.75}
                      disabled={isCurrent || checkoutLoading === plan.id}
                      style={[
                        styles.planAction,
                        {
                          backgroundColor: isCurrent ? 'rgba(52,199,89,0.12)' : '#007AFF',
                        },
                      ]}
                      onPress={() => startCheckout(plan.id)}
                    >
                      <Text style={[
                        styles.planActionText,
                        { color: isCurrent ? '#34C759' : '#FFFFFF' },
                      ]}>
                        {isCurrent ? '当前套餐' : checkoutLoading === plan.id ? '正在切换...' : '切换套餐'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                );
              })}
              {!!checkoutError && (
                <Text style={styles.checkoutError}>{checkoutError}</Text>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Memory Modal */}
      <Modal animationType="slide" transparent visible={memoryModalVisible} onRequestClose={() => setMemoryModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.memoryModal, { backgroundColor: cardBg, borderColor: borderCol }]}>
            <View style={styles.memModalHeader}>
              <Text style={[styles.cardTitle, { color: textCol }]}>AI 记忆浏览器</Text>
              <TouchableOpacity activeOpacity={0.7} style={[styles.closeCircle, { backgroundColor: isDark ? '#2C2C30' : '#E5E5EA' }]}
                onPress={() => setMemoryModalVisible(false)}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: textCol }}>✕</Text>
              </TouchableOpacity>
            </View>
            {memoryLoading ? (
              <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                <ActivityIndicator size="large" color="#007AFF" />
                <Text style={{ color: subTextCol, marginTop: 12 }}>加载中...</Text>
              </View>
            ) : memoryData ? (
              <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>
                {[{ title: 'Layer 1: 核心画像', data: Object.fromEntries(Object.entries(memoryData.profile || {}).filter(([k]) => k !== 'metrics' && k !== 'user_id')) },
                  { title: 'Layer 2: 动态指标', data: Object.fromEntries(Object.entries(memoryData.profile?.metrics || {}).map(([k, v]: any) => [k, `${v.value} ${v.unit}`])) },
                ].map((section, si) => (
                  <View key={si}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: '#007AFF', marginBottom: 8, marginTop: si > 0 ? 14 : 0, textTransform: 'uppercase', letterSpacing: 0.8 }}>{section.title}</Text>
                    <View style={{ borderWidth: 0.5, borderRadius: 12, padding: 12, borderColor: borderCol }}>
                      {Object.keys(section.data).length > 0 ? Object.entries(section.data).map(([k, v]) => (
                        <View key={k} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5 }}>
                          <Text style={{ fontSize: 12, color: subTextCol }}>{k}</Text>
                          <Text style={{ fontSize: 12, fontWeight: '600', color: textCol }}>{String(v)}</Text>
                        </View>
                      )) : <Text style={{ color: subTextCol, fontSize: 12 }}>无</Text>}
                    </View>
                  </View>
                ))}
                <Text style={{ fontSize: 11, fontWeight: '800', color: '#007AFF', marginTop: 14, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.8 }}>Layer 3: 近期事件</Text>
                <View style={{ borderWidth: 0.5, borderRadius: 12, padding: 12, borderColor: borderCol }}>
                  {(memoryData.recent_events || []).length > 0
                    ? memoryData.recent_events.slice(0, 20).map((ev: any, i: number) => {
                        const isExpanded = expandedEventIndex === i;
                        return (
                          <TouchableOpacity 
                            key={i} 
                            activeOpacity={0.7}
                            onPress={() => setExpandedEventIndex(isExpanded ? null : i)}
                            style={{ paddingVertical: 6, borderBottomWidth: i < memoryData.recent_events.length - 1 ? 0.5 : 0, borderBottomColor: borderCol }}
                          >
                            <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                              <View style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: ev.type === 'training' ? 'rgba(0,122,255,0.1)' : ev.type === 'diet' ? 'rgba(52,199,89,0.1)' : 'rgba(255,149,0,0.1)' }}>
                                <Text style={{ fontSize: 9, fontWeight: '700', color: ev.type === 'training' ? '#007AFF' : ev.type === 'diet' ? '#34C759' : '#FF9500' }}>{ev.type}</Text>
                              </View>
                              <Text style={{ fontSize: 10, color: subTextCol, width: 72 }}>{ev.date}</Text>
                              {!isExpanded && (
                                <Text style={{ fontSize: 10, color: textCol, flex: 1 }} numberOfLines={1}>
                                  {JSON.stringify(ev.payload)}
                                </Text>
                              )}
                            </View>
                            {isExpanded && (
                              <View style={{ marginTop: 8, padding: 8, backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)', borderRadius: 8 }}>
                                <Text style={{ fontSize: 10, color: textCol, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }) }}>
                                  {JSON.stringify(ev.payload, null, 2)}
                                </Text>
                              </View>
                            )}
                          </TouchableOpacity>
                        );
                      })
                    : <Text style={{ color: subTextCol, fontSize: 12 }}>无</Text>}
                </View>

                {/* Mem0 AI Long Term Memory */}
                <Text style={{ fontSize: 11, fontWeight: '800', color: '#007AFF', marginTop: 14, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.8 }}>Mem0: 深度语义记忆</Text>
                <View style={{ borderWidth: 0.5, borderRadius: 12, padding: 12, borderColor: borderCol }}>
                  {(mem0Data || []).length > 0
                    ? mem0Data.map((mem: any, i: number) => (
                      <View key={i} style={{ paddingVertical: 5 }}>
                        <Text style={{ fontSize: 12, color: textCol }}>• {mem.memory}</Text>
                        <Text style={{ fontSize: 10, color: subTextCol, marginTop: 2 }}>{new Date(mem.created_at).toLocaleString()}</Text>
                      </View>
                    ))
                    : <Text style={{ color: subTextCol, fontSize: 12 }}>无 Mem0 记忆记录</Text>}
                </View>
              </ScrollView>
            ) : (
              <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ color: subTextCol }}>暂无数据</Text>
              </View>
            )}
            <TouchableOpacity activeOpacity={0.7} style={{ margin: 14, paddingVertical: 14, borderRadius: 14, backgroundColor: '#007AFF', alignItems: 'center' }} onPress={fetchMemory}>
              <Text style={{ color: '#FFFFFF', fontWeight: '700' }}>刷新</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContent: { paddingHorizontal: Spacing.four },
  container: { maxWidth: MaxContentWidth, alignSelf: 'center', width: '100%', gap: Spacing.four },
  header: { marginTop: Spacing.two, marginBottom: Spacing.two },
  headerTitle: { fontWeight: 'bold', fontSize: 24 },
  headerSubtitle: { fontSize: 13, marginTop: 4 },
  card: { borderRadius: 14, borderWidth: 0.5, shadowColor: '#000', shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.05, shadowRadius: 8, elevation: 1 },
  cardTitle: { fontWeight: 'bold', fontSize: 14, marginBottom: 8 },
  // Account
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  accountActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  acLabel: { fontSize: 10, marginBottom: 3 },
  acId: { fontSize: 11, fontWeight: '600', fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }), marginBottom: 6 },
  acMeta: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  statusBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5 },
  statusBadgeText: { fontSize: 9, fontWeight: '700' },
  acMetaText: { fontSize: 9 },
  loginBtn: { backgroundColor: '#007AFF', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 10 },
  loginBtnText: { color: '#FFFFFF', fontWeight: '700', fontSize: 12 },
  upgradeBtn: { backgroundColor: '#007AFF', paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10 },
  upgradeBtnText: { color: '#FFFFFF', fontWeight: '700', fontSize: 12 },
  logoutBtn: { backgroundColor: 'rgba(255,59,48,0.08)', borderWidth: 1, borderColor: 'rgba(255,59,48,0.2)', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 10 },
  logoutBtnText: { color: '#FF3B30', fontWeight: '700', fontSize: 12 },
  // Memory
  memHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  viewMemBtn: { paddingVertical: 5, paddingHorizontal: 10, borderRadius: 6, backgroundColor: 'rgba(0,122,255,0.06)' },
  viewMemBtnText: { color: '#007AFF', fontSize: 11, fontWeight: '600' },
  memDesc: { fontSize: 11, lineHeight: 18 },
  planSubtitle: { fontSize: 11, lineHeight: 16 },
  quotaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  quotaItem: { flex: 1, minWidth: '44%', padding: 10, backgroundColor: 'rgba(88,86,214,0.05)', borderRadius: 9 },
  quotaVal: { fontWeight: '800', fontSize: 14, marginTop: 3 },
  // Stats
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  statItem: { flex: 1, minWidth: '44%', padding: 8, backgroundColor: 'rgba(0,122,255,0.03)', borderRadius: 8 },
  statLabel: { fontSize: 9, color: '#8E8E93', marginBottom: 2 },
  statVal: { fontWeight: 'bold', fontSize: 15 },
  statUnit: { fontSize: 11, color: '#8E8E93', fontWeight: 'normal' },
  nutritionDetailCard: { marginTop: 12, borderRadius: 12, padding: 12 },
  nutritionDetailHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  nutritionDetailTitle: { fontSize: 13, fontWeight: '800' },
  nutritionMealType: { fontSize: 11, fontWeight: '600' },
  nutritionFoods: { marginTop: 6, fontSize: 11, lineHeight: 17 },
  nutritionMacroRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  nutritionMacroItem: { flex: 1, minWidth: '44%', padding: 10, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.04)' },
  nutritionMacroValue: { fontSize: 14, fontWeight: '800', marginTop: 2 },
  // Modals
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  loginModal: { width: '100%', maxWidth: 380, borderRadius: 24, borderWidth: 0.5, padding: 28 },
  loginTitle: { fontSize: 22, fontWeight: '800', textAlign: 'center', marginBottom: 6 },
  loginSub: { fontSize: 13, textAlign: 'center', marginBottom: 24 },
  presetBtn: { padding: 14, borderRadius: 14, gap: 2 },
  presetBtnLabel: { fontSize: 14, fontWeight: '700' },
  presetBtnId: { fontSize: 10, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }) },
  loginDivider: { textAlign: 'center', fontSize: 12, marginBottom: 18 },
  loginInput: { borderWidth: 1, borderRadius: 14, padding: 14, fontSize: 14, marginBottom: 14, fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }) },
  loginConfirmBtn: { borderRadius: 16, paddingVertical: 16, alignItems: 'center', backgroundColor: '#007AFF', marginBottom: 10 },
  authSwitch: { flexDirection: 'row', backgroundColor: 'rgba(142,142,147,0.12)', borderRadius: 12, padding: 3, marginBottom: 16 },
  authSwitchBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 9 },
  authSwitchBtnActive: { backgroundColor: '#007AFF' },
  authSwitchText: { fontSize: 12, fontWeight: '700' },
  plansModal: { width: '100%', maxWidth: 680, maxHeight: '84%', borderRadius: 24, borderWidth: 0.5, overflow: 'hidden' },
  planList: { padding: 16, gap: 12 },
  planCard: { borderWidth: 1, borderRadius: 14, padding: 14, gap: 12 },
  planTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  planTitle: { fontSize: 18, fontWeight: '800' },
  planPrice: { fontSize: 18, fontWeight: '900' },
  planMetaRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  planMeta: { fontSize: 11, fontWeight: '600' },
  featureWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  featurePill: { paddingVertical: 4, paddingHorizontal: 8, borderRadius: 8, backgroundColor: 'rgba(0,122,255,0.1)' },
  featurePillText: { color: '#007AFF', fontSize: 10, fontWeight: '700' },
  planAction: { borderRadius: 12, paddingVertical: 12, alignItems: 'center' },
  planActionText: { fontSize: 13, fontWeight: '800' },
  checkoutError: { color: '#FF3B30', fontSize: 12, textAlign: 'center', marginTop: 2 },
  memoryModal: { width: '100%', maxWidth: 680, height: '82%', borderRadius: 24, borderWidth: 0.5, overflow: 'hidden' },
  memModalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, borderBottomWidth: 0.5, borderBottomColor: '#2C2C2E' },
  closeCircle: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center' },
});
