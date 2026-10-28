import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Switch,
  Alert} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import Constants from 'expo-constants';
import { Colors, Spacing, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { api, getAuthToken, removeAuthToken } from '@/services/api';
import { useStylingSession } from '@/services/session';

export default function ProfileScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const [highQuality, setHighQuality] = useState(true);
  const [cloudGpuMode, setCloudGpuMode] = useState(false);
  const [profile, setProfile] = useState<{
    name: string;
    email: string;
    saved_looks_count: number;
    tryons_count: number;
    wardrobe_count: number;
    is_admin: boolean;
  } | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const token = await getAuthToken();
      setIsAuthenticated(Boolean(token));
      if (!token) {
        setProfile(null);
        return;
      }
      const p = await api.profile.get();
      setProfile({
        name: p.name,
        email: p.email,
        saved_looks_count: p.saved_looks_count ?? 0,
        tryons_count: p.tryons_count ?? 0,
        wardrobe_count: p.wardrobe_count ?? 0,
        is_admin: Boolean(p.is_admin),
      });
    } catch {
      setProfile(null);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadProfile();
    }, [loadProfile])
  );

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'Sign out of your StyleVision account?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          session.resetSession();
          await removeAuthToken();
          setIsAuthenticated(false);
          setProfile(null);
          router.replace('/(auth)/login');
        },
      },
    ]);
  };

  const handleClearCache = () => {
    Alert.alert('Cache Cleared', 'Local image cache and temporary uploads have been cleared.');
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>VIP Atelier Suite</Text>
        </View>

        {/* User Card */}
        <Card style={styles.userCard} variant="elevated">
          <View style={styles.userRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarEmoji}>👑</Text>
            </View>
            <View style={styles.userInfo}>
              <View style={styles.nameRow}>
                <Text style={styles.userName}>
                  {profile?.name ?? 'Prestige Atelier Member'}
                </Text>
                <Badge label="VIP HAUTE" variant="primary" style={styles.badge} />
              </View>
              <Text style={styles.userEmail}>{profile?.email ?? 'Not signed in'}</Text>
            </View>
          </View>
          <View style={styles.authActions}>
            {isAuthenticated ? (
              <Button
                title="Sign Out"
                variant="outline"
                size="sm"
                onPress={handleSignOut}
                style={styles.authBtn}
              />
            ) : (
              <Button
                title="Atelier Authentication"
                variant="outline"
                size="sm"
                onPress={() => router.push('/(auth)/login')}
                style={styles.authBtn}
              />
            )}
          </View>
        </Card>

        {/* Stats Row — live counts from the user's account */}
        <View style={styles.statsRow}>
          <Card style={styles.statCard} variant="flat">
            <Text style={styles.statNumber}>{profile?.tryons_count ?? '—'}</Text>
            <Text style={styles.statLabel}>Fittings</Text>
          </Card>
          <Card style={styles.statCard} variant="flat">
            <Text style={styles.statNumber}>{profile?.saved_looks_count ?? '—'}</Text>
            <Text style={styles.statLabel}>Lookbook</Text>
          </Card>
          <Card style={styles.statCard} variant="flat">
            <Text style={styles.statNumber}>{profile?.wardrobe_count ?? '—'}</Text>
            <Text style={styles.statLabel}>Wardrobe</Text>
          </Card>
        </View>

        {/* AI & Performance Settings */}
        <Text style={styles.sectionHeading}>AI & Inference Preferences</Text>
        <Card style={styles.settingsCard} variant="outlined">
          <View style={styles.settingRow}>
            <View style={styles.settingTextWrap}>
              <Text style={styles.settingTitle}>CatVTON Cloud GPU Mode</Text>
              <Text style={styles.settingDesc}>
                Route clothing try-ons through remote Colab T4 GPU (prototype overlay on CPU)
              </Text>
            </View>
            <Switch
              value={cloudGpuMode}
              onValueChange={setCloudGpuMode}
              trackColor={{ false: Colors.surface, true: Colors.primary }}
              thumbColor={Colors.textPrimary}
            />
          </View>

          <View style={styles.divider} />

          <View style={styles.settingRow}>
            <View style={styles.settingTextWrap}>
              <Text style={styles.settingTitle}>High-Resolution Output</Text>
              <Text style={styles.settingDesc}>Generate high-detail 1024x768 render comparisons</Text>
            </View>
            <Switch
              value={highQuality}
              onValueChange={setHighQuality}
              trackColor={{ false: Colors.surface, true: Colors.primary }}
              thumbColor={Colors.textPrimary}
            />
          </View>
        </Card>

        {/* Privacy & Storage */}
        <Text style={styles.sectionHeading}>Privacy & Storage</Text>
        <Card style={styles.settingsCard} variant="outlined">
          <TouchableOpacity
            style={styles.actionRow}
            onPress={handleClearCache}
          >
            <Text style={styles.actionTitle}>Clear Local Upload Cache</Text>
            <Text style={styles.actionChevron}>🗑️</Text>
          </TouchableOpacity>

          <View style={styles.divider} />

          {profile?.is_admin && (
            <>
              <View style={styles.divider} />
              <TouchableOpacity
                style={styles.actionRow}
                onPress={() => router.push('/admin/catalogue')}
              >
                <Text style={styles.actionTitle}>Admin Catalogue Management</Text>
                <Text style={styles.actionChevron}>⚙️</Text>
              </TouchableOpacity>
            </>
          )}
        </Card>

        {/* App Info Card */}
        <Card style={styles.infoCard} variant="flat">
          <Text style={styles.infoTitle}>About StyleVision</Text>
          <Text style={styles.infoText}>
            StyleVision is an intelligent virtual styling studio enabling seamless try-on for outfits, fine jewelry, hairstyles, and makeup on your portrait.{'\n\n'}
            • App Version: v{Constants.expoConfig?.version ?? '1.0.0'}{'\n'}
            • Privacy: 100% Protected and secure processing
          </Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background},
  container: {
    flex: 1,
    backgroundColor: Colors.background},
  content: {
    padding: Spacing.xl,
    paddingBottom: Spacing.xxxl * 2},
  header: {
    marginBottom: Spacing.xl},
  title: {
    fontSize: Typography.sizes.xxl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary},
  userCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.lg,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.borderLight},
  userRow: {
    flexDirection: 'row',
    alignItems: 'center'},
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: Colors.primaryGlow,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.lg,
    borderWidth: 1.5,
    borderColor: Colors.primary},
  avatarEmoji: {
    fontSize: 26},
  userInfo: {
    flex: 1},
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4},
  userName: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginRight: Spacing.sm},
  badge: {
    paddingVertical: 1},
  userEmail: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted},
  authActions: {
    marginTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    paddingTop: Spacing.md},
  authBtn: {
    alignSelf: 'stretch'},
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: Spacing.xxl},
  statCard: {
    width: '31%',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border},
  statNumber: {
    fontSize: Typography.sizes.xl,
    fontWeight: Typography.weights.heavy,
    color: Colors.primaryLight},
  statLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2},
  sectionHeading: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: Spacing.sm},
  settingsCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    marginBottom: Spacing.xxl},
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'},
  settingTextWrap: {
    flex: 1,
    paddingRight: Spacing.md},
  settingTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2},
  settingDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    lineHeight: 16},
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md},
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Spacing.xs},
  actionTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.medium,
    color: Colors.textPrimary},
  actionChevron: {
    fontSize: 16},
  infoCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border},
  infoTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
    marginBottom: Spacing.sm},
  infoText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    lineHeight: 20}});
