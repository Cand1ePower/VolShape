import React, { useState } from 'react';
import {
  ScrollView, View, Text, StyleSheet, useColorScheme, Platform,
  TouchableOpacity, useWindowDimensions, Modal, ActivityIndicator, TextInput,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '@/contexts/AuthContext';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';

export default function ExploreScreen() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const safeAreaInsets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const { token, userId, isLoggedIn, login, logout } = useAuth();

  const insets = { ...safeAreaInsets, bottom: safeAreaInsets.bottom + BottomTabInset + Spacing.three };
  const isSmallScreen = width < 375;
  const dynamicPadding = isSmallScreen ? 14 : 18;

  const bgCol = isDark ? '#000000' : '#F2F2F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFFFFF';
  const borderCol = isDark ? '#2C2C2E' : '#E5E5EA';
  const textCol = isDark ? '#FFFFFF' : '#000000';
  const subTextCol = isDark ? '#AEAEB2' : '#8E8E93';

  // Login modal
  const [loginModalVisible, setLoginModalVisible] = useState(false);
  const [devUserId, setDevUserId] = useState('test-user-vip-candlepw');

  // Memory viewer modal
  const [memoryModalVisible, setMemoryModalVisible] = useState(false);
  const [memoryData, setMemoryData] = useState<any>(null);
  const [memoryLoading, setMemoryLoading] = useState(false);

  const fetchMemory = async () => {
    setMemoryLoading(true);
    setMemoryModalVisible(true);
    try {
      const baseUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
      const response = await fetch(`${baseUrl}/api/chat/profile`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await response.json();
      setMemoryData(data);
    } catch (err) {
      console.error('Failed to fetch memory:', err);
    } finally {
      setMemoryLoading(false);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: bgCol }} contentInset={insets} contentContainerStyle={[styles.scrollContent, {
      paddingTop: Platform.OS === 'android' ? insets.top + Spacing.two : Spacing.four,
      paddingBottom: insets.bottom,
    }]}>
      <View style={styles.container}>
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
                <Text style={[styles.acId, { color: textCol }]} numberOfLines={1}>{isLoggedIn ? userId : '未登录'}</Text>
                {isLoggedIn && (
                  <View style={[styles.statusBadge, { backgroundColor: userId?.includes('vip') ? 'rgba(255,215,0,0.15)' : 'rgba(0,122,255,0.1)' }]}>
                    <Text style={[styles.statusBadgeText, { color: userId?.includes('vip') ? '#FFD700' : '#007AFF' }]}>
                      {userId?.includes('vip') ? 'VIP' : 'Free'}
                    </Text>
                  </View>
                )}
              </View>
            </View>
            {isLoggedIn ? (
              <TouchableOpacity activeOpacity={0.7} style={styles.logoutBtn} onPress={logout}>
                <Text style={styles.logoutBtnText}>退出</Text>
              </TouchableOpacity>
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
        </View>

        {/* Quick Stats */}
        <View style={[styles.card, { backgroundColor: cardBg, borderColor: borderCol, padding: dynamicPadding }]}>
          <Text style={[styles.cardTitle, { color: textCol }]}>健康仪表盘</Text>
          <View style={styles.statGrid}>
            {[{ label: '身高', val: '175', unit: 'cm' }, { label: '体重', val: '64.0', unit: 'kg' }, { label: '体脂', val: '17', unit: '%' }, { label: '目标', val: '减脂', unit: '' }].map((s, i) => (
              <View key={i} style={styles.statItem}>
                <Text style={styles.statLabel}>{s.label}</Text>
                <Text style={[styles.statVal, { color: textCol }]}>{s.val}<Text style={styles.statUnit}> {s.unit}</Text></Text>
              </View>
            ))}
          </View>
        </View>

        <View style={{ height: Spacing.four }} />
      </View>

      {/* Login Modal */}
      <Modal animationType="slide" transparent visible={loginModalVisible} onRequestClose={() => setLoginModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.loginModal, { backgroundColor: cardBg, borderColor: borderCol }]}>
            <Text style={[styles.loginTitle, { color: textCol }]}>登录</Text>
            <Text style={[styles.loginSub, { color: subTextCol }]}>选择预设账号或输入自定义 ID</Text>
            <View style={{ gap: 10, marginBottom: 20 }}>
              <TouchableOpacity activeOpacity={0.7} style={[styles.presetBtn, { backgroundColor: isDark ? '#2C2C30' : '#F0F0F3' }]}
                onPress={() => { login('test-user-vip-candlepw'); setLoginModalVisible(false); }}>
                <Text style={[styles.presetBtnLabel, { color: textCol }]}>⭐ VIP</Text>
                <Text style={[styles.presetBtnId, { color: subTextCol }]}>test-user-vip-candlepw</Text>
              </TouchableOpacity>
              <TouchableOpacity activeOpacity={0.7} style={[styles.presetBtn, { backgroundColor: isDark ? '#2C2C30' : '#F0F0F3' }]}
                onPress={() => { login('test-user-free-candlepw'); setLoginModalVisible(false); }}>
                <Text style={[styles.presetBtnLabel, { color: textCol }]}>🆓 免费</Text>
                <Text style={[styles.presetBtnId, { color: subTextCol }]}>test-user-free-candlepw</Text>
              </TouchableOpacity>
            </View>
            <Text style={[styles.loginDivider, { color: subTextCol }]}>—— 自定义 ——</Text>
            <TextInput style={[styles.loginInput, { color: textCol, borderColor: borderCol, backgroundColor: isDark ? '#0A0A0C' : '#F5F5F7' }]}
              value={devUserId} onChangeText={setDevUserId} placeholder="输入 userId..." placeholderTextColor={subTextCol} />
            <TouchableOpacity activeOpacity={0.7} style={styles.loginConfirmBtn}
              onPress={() => { login(devUserId.startsWith('test-user-') ? devUserId : `test-user-${devUserId}`); setLoginModalVisible(false); }}>
              <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 15 }}>确认登录</Text>
            </TouchableOpacity>
            <TouchableOpacity activeOpacity={0.7} onPress={() => setLoginModalVisible(false)} style={{ alignItems: 'center', paddingVertical: 8 }}>
              <Text style={{ color: '#007AFF', fontSize: 14 }}>取消</Text>
            </TouchableOpacity>
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
                    ? memoryData.recent_events.slice(0, 20).map((ev: any, i: number) => (
                      <View key={i} style={{ flexDirection: 'row', paddingVertical: 5, gap: 8, alignItems: 'center' }}>
                        <View style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: ev.type === 'training' ? 'rgba(0,122,255,0.1)' : ev.type === 'diet' ? 'rgba(52,199,89,0.1)' : 'rgba(255,149,0,0.1)' }}>
                          <Text style={{ fontSize: 9, fontWeight: '700', color: ev.type === 'training' ? '#007AFF' : ev.type === 'diet' ? '#34C759' : '#FF9500' }}>{ev.type}</Text>
                        </View>
                        <Text style={{ fontSize: 10, color: subTextCol, width: 72 }}>{ev.date}</Text>
                        <Text style={{ fontSize: 10, color: textCol, flex: 1 }} numberOfLines={1}>{JSON.stringify(ev.payload)}</Text>
                      </View>
                    ))
                    : <Text style={{ color: subTextCol, fontSize: 12 }}>无</Text>}
                </View>
              </ScrollView>
            ) : (
              <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ color: subTextCol }}>暂无数据</Text>
              </View>
            )}
            <TouchableOpacity activeOpacity={0.7} style={{ margin: 14, paddingVertical: 14, borderRadius: 14, backgroundColor: '#007AFF', alignItems: 'center' }} onPress={fetchMemory}>
              <Text style={{ color: '#FFFFFF', fontWeight: '700' }}>🔄 刷新</Text>
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
  card: { borderRadius: 20, borderWidth: 0.5, shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 12, elevation: 2 },
  cardTitle: { fontWeight: 'bold', fontSize: 15, marginBottom: 12 },
  // Account
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  acLabel: { fontSize: 11, marginBottom: 4 },
  acId: { fontSize: 12, fontWeight: '600', fontFamily: Platform.select({ ios: 'CourierNewPSMT', android: 'monospace', web: 'monospace' }), marginBottom: 8 },
  acMeta: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  statusBadgeText: { fontSize: 10, fontWeight: '700' },
  acMetaText: { fontSize: 10 },
  loginBtn: { backgroundColor: '#007AFF', paddingVertical: 10, paddingHorizontal: 18, borderRadius: 12 },
  loginBtnText: { color: '#FFFFFF', fontWeight: '700', fontSize: 13 },
  logoutBtn: { backgroundColor: 'rgba(255,59,48,0.1)', borderWidth: 1, borderColor: 'rgba(255,59,48,0.3)', paddingVertical: 10, paddingHorizontal: 18, borderRadius: 12 },
  logoutBtnText: { color: '#FF3B30', fontWeight: '700', fontSize: 13 },
  // Memory
  memHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  viewMemBtn: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: 8, backgroundColor: 'rgba(0,122,255,0.08)' },
  viewMemBtnText: { color: '#007AFF', fontSize: 12, fontWeight: '600' },
  memDesc: { fontSize: 12, lineHeight: 20 },
  // Stats
  statGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  statItem: { flex: 1, minWidth: '44%', padding: 10, backgroundColor: 'rgba(0,122,255,0.04)', borderRadius: 10 },
  statLabel: { fontSize: 10, color: '#8E8E93', marginBottom: 4 },
  statVal: { fontWeight: 'bold', fontSize: 18 },
  statUnit: { fontSize: 12, color: '#8E8E93', fontWeight: 'normal' },
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
  memoryModal: { width: '100%', maxWidth: 680, height: '82%', borderRadius: 24, borderWidth: 0.5, overflow: 'hidden' },
  memModalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 20, borderBottomWidth: 0.5, borderBottomColor: '#2C2C2E' },
  closeCircle: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center' },
});
