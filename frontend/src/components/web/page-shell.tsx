import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

type WebPageShellProps = {
  backgroundColor: string;
  children: ReactNode;
  contentMaxWidth?: number;
  contentContainerStyle?: any;
};

export function WebPageShell({
  backgroundColor,
  children,
  contentMaxWidth = 1240,
  contentContainerStyle,
}: WebPageShellProps) {
  return (
    <ScrollView
      style={[styles.page, { backgroundColor }]}
      contentContainerStyle={[styles.pageContent, contentContainerStyle]}
      contentInsetAdjustmentBehavior="automatic"
    >
      <View style={[styles.inner, { maxWidth: contentMaxWidth }]}>{children}</View>
    </ScrollView>
  );
}

type WebPanelProps = {
  backgroundColor: string;
  borderColor: string;
  children: ReactNode;
  style?: any;
};

export function WebPanel({ backgroundColor, borderColor, children, style }: WebPanelProps) {
  return <View style={[styles.panel, { backgroundColor, borderColor }, style]}>{children}</View>;
}

type WebSectionHeadingProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  textColor: string;
  subTextColor: string;
};

export function WebSectionHeading({
  eyebrow,
  title,
  subtitle,
  textColor,
  subTextColor,
}: WebSectionHeadingProps) {
  return (
    <View style={styles.sectionHeading}>
      {eyebrow ? <Text style={[styles.eyebrow, { color: subTextColor }]}>{eyebrow}</Text> : null}
      <Text style={[styles.title, { color: textColor }]}>{title}</Text>
      {subtitle ? <Text style={[styles.subtitle, { color: subTextColor }]}>{subtitle}</Text> : null}
    </View>
  );
}

type WebMetricProps = {
  label: string;
  value: string;
  textColor: string;
  subTextColor: string;
  style?: any;
};

export function WebMetric({ label, value, textColor, subTextColor, style }: WebMetricProps) {
  return (
    <View style={[styles.metric, style]}>
      <Text style={[styles.metricLabel, { color: subTextColor }]}>{label}</Text>
      <Text style={[styles.metricValue, { color: textColor }]}>{value}</Text>
    </View>
  );
}

type WebActionChipProps = {
  label: string;
  onPress?: () => void;
  icon?: ReactNode;
  textColor: string;
  backgroundColor: string;
  borderColor: string;
};

export function WebActionChip({
  label,
  onPress,
  icon,
  textColor,
  backgroundColor,
  borderColor,
}: WebActionChipProps) {
  return (
    <Pressable
      onPress={onPress}
      style={({ hovered, pressed }) => [
        styles.actionChip,
        {
          backgroundColor,
          borderColor,
          opacity: pressed ? 0.9 : 1,
          transform: [{ translateY: hovered ? -1 : 0 }],
          boxShadow: hovered ? '0 14px 34px rgba(15, 23, 42, 0.14)' : '0 8px 20px rgba(15, 23, 42, 0.08)',
        } as any,
      ]}
    >
      {icon}
      <Text style={[styles.actionChipText, { color: textColor }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
  },
  pageContent: {
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 48,
  },
  inner: {
    width: '100%',
    alignSelf: 'center',
    gap: 20,
  },
  panel: {
    borderWidth: 1,
    borderRadius: 30,
    padding: 24,
  },
  sectionHeading: {
    gap: 8,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  title: {
    fontSize: 30,
    lineHeight: 36,
    fontWeight: '800',
    letterSpacing: -0.9,
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 22,
    maxWidth: 760,
  },
  metric: {
    minWidth: 118,
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: 'rgba(255,255,255,0.04)',
    gap: 4,
  },
  metricLabel: {
    fontSize: 11,
    fontWeight: '600',
  },
  metricValue: {
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: -0.3,
  },
  actionChip: {
    minHeight: 42,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    transitionDuration: '180ms',
  } as any,
  actionChipText: {
    fontSize: 13,
    fontWeight: '700',
  },
});
