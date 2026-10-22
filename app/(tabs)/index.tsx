import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  RefreshControl} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import Constants from 'expo-constants';
import { Colors, Spacing, BorderRadius, Typography, Shadows } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { api, getAuthToken, getApiBaseUrl } from '@/services/api';



export default function HomeDashboard() {
  const router = useRouter();
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [backendDetails, setBackendDetails] = useState<string>('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const checkHealth = async () => {
    try {
      setBackendStatus('checking');
      const data = await api.health();
      setBackendStatus('connected');
      setBackendDetails(`${data.app} v${data.version} (${data.tryon_mode} mode)`);
    } catch (err: any) {
      setBackendStatus('disconnected');
      setBackendDetails(err.message || 'Unreachable');
    }

    try {
      const token = await getAuthToken();
      if (token) {
        const me = await api.auth.getMe();
        setIsAdmin(Boolean(me?.is_admin));
      } else {
        setIsAdmin(false);
      }
    } catch {
      setIsAdmin(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await checkHealth();
    setRefreshing(false);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={Colors.primary}
          />
        }
      >
        {/* Top Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.brandTitle}>STYLEVISION</Text>
            <Text style={styles.brandSubtitle}>Haute Couture Virtual Atelier</Text>
          </View>
          <TouchableOpacity
            style={styles.avatarButton}
            onPress={() => router.push('/(tabs)/profile')}
            accessibilityLabel="Open VIP Suite"
          >
            <Text style={styles.avatarText}>👑</Text>
          </TouchableOpacity>
        </View>

        {/* Backend Connection Status Pill */}
        <Card style={styles.statusCard} variant="flat">
          <View style={styles.statusRow}>
            <View style={styles.statusIndicator}>
              <View
                style={[
                  styles.statusDot,
                  backendStatus === 'connected' && styles.statusConnected,
                  backendStatus === 'disconnected' && styles.statusDisconnected,
                  backendStatus === 'checking' && styles.statusChecking,
                ]}
              />
              <Text style={styles.statusText}>
                {backendStatus === 'connected'
                  ? `Atelier Engine Active: ${backendDetails}`
                  : backendStatus === 'checking'
                  ? 'Connecting to atelier engine...'
                  : `Engine offline (${getApiBaseUrl()})`}
              </Text>
            </View>
            <TouchableOpacity onPress={checkHealth}>
              <Text style={styles.refreshText}>↻</Text>
            </TouchableOpacity>
          </View>
        </Card>

        {/* Hero Banner */}
        <Card style={styles.heroCard} variant="elevated">
          <Badge label="PRESTIGE AI ATELIER" variant="primary" style={styles.heroBadge} />
          <Text style={styles.heroHeading}>The Art of Virtual High Fashion</Text>
          <Text style={styles.heroBody}>
            Experience hyper-realistic fitting of luxury garments, fine jewelry, haute coiffure,
            and beauty artistry directly on your portrait with sub-pixel anatomical precision.
          </Text>
          <Button
            title="Explore The Studios ✨"
            variant="primary"
            size="md"
            onPress={() => router.push('/(tabs)/try-on')}
            style={styles.heroButton}
          />
        </Card>

        {/* Category Shortcuts Section */}
        <Text style={styles.sectionHeading}>Couture Studios</Text>
        <View style={styles.categoriesGrid}>
          {/* Outfits */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/outfit')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>👗</Text>
            </View>
            <Text style={styles.categoryTitle}>Haute Wardrobe</Text>
            <Text style={styles.categoryDesc}>Bespoke couture & jacket fitting</Text>
            <Badge label="Neural AI" variant="primary" style={styles.categoryBadge} />
          </Card>

          {/* Accessories */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/accessories')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>💎</Text>
            </View>
            <Text style={styles.categoryTitle}>Jewelry & Optics</Text>
            <Text style={styles.categoryDesc}>Diamonds, aviators & totes</Text>
            <Badge label="Anatomical" variant="success" style={styles.categoryBadge} />
          </Card>

          {/* Makeup */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/makeup')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>💄</Text>
            </View>
            <Text style={styles.categoryTitle}>Beauty Artistry</Text>
            <Text style={styles.categoryDesc}>Luxe lipsticks, eye & contour</Text>
            <Badge label="Mesh Blend" variant="warning" style={styles.categoryBadge} />
          </Card>

          {/* Hairstyles */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/hairstyle')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>✂️</Text>
            </View>
            <Text style={styles.categoryTitle}>Haute Coiffure</Text>
            <Text style={styles.categoryDesc}>Designer cuts, waves & tints</Text>
            <Badge label="Cranial Pose" variant="muted" style={styles.categoryBadge} />
          </Card>
        </View>

        {/* How It Works Guide */}
        <Text style={styles.sectionHeading}>The Atelier Process</Text>
        <Card style={styles.stepsCard} variant="outlined">
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>1</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Portrait Calibration</Text>
              <Text style={styles.stepDesc}>Upload a front-facing portrait to anchor your personalized digital avatar.</Text>
            </View>
          </View>
          <View style={styles.stepDivider} />
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>2</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Curate Desired Look</Text>
              <Text style={styles.stepDesc}>Browse garments, diamond accessories, curated palettes, or hairstyles.</Text>
            </View>
          </View>
          <View style={styles.stepDivider} />
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>3</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Precision Synthesis</Text>
              <Text style={styles.stepDesc}>Experience flawless anatomical draping preserving your authentic identity.</Text>
            </View>
          </View>
        </Card>

        {/* Admin Portal Shortcut (Admins Only) */}
        {isAdmin && (
          <Card
            style={styles.adminCard}
            variant="flat"
            onPress={() => router.push('/admin/catalogue')}
          >
            <View style={styles.adminRow}>
              <View>
                <Text style={styles.adminTitle}>Atelier Catalogue Management</Text>
                <Text style={styles.adminSubtitle}>Curate wardrobe archives & designer items</Text>
              </View>
              <Text style={styles.adminArrow}>➔</Text>
            </View>
          </Card>
        )}

        {/* Footer */}
        <Text style={styles.footerText}>
          STYLEVISION · Haute Couture AI Engine
        </Text>
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.lg},
  brandTitle: {
    fontSize: Typography.sizes.xxl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
    letterSpacing: 0.5},
  brandSubtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    marginTop: 2},
  avatarButton: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: Colors.border},
  avatarText: {
    fontSize: 20},
  statusCard: {
    padding: Spacing.sm + 2,
    marginBottom: Spacing.lg,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border},
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'},
  statusIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1},
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: Spacing.sm},
  statusConnected: {
    backgroundColor: Colors.success},
  statusDisconnected: {
    backgroundColor: Colors.error},
  statusChecking: {
    backgroundColor: Colors.warning},
  statusText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    flex: 1},
  refreshText: {
    fontSize: 16,
    color: Colors.primaryLight,
    paddingHorizontal: Spacing.sm},
  heroCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.xxl,
    marginBottom: Spacing.xxl,
    borderWidth: 1,
    borderColor: Colors.borderLight,
    ...Shadows.glow},
  heroBadge: {
    marginBottom: Spacing.md},
  heroHeading: {
    fontSize: Typography.sizes.xl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
    marginBottom: Spacing.sm},
  heroBody: {
    fontSize: Typography.sizes.sm,
    color: Colors.textSecondary,
    lineHeight: 20,
    marginBottom: Spacing.lg},
  heroButton: {
    alignSelf: 'stretch'},
  sectionHeading: {
    fontSize: Typography.sizes.lg,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: Spacing.md},
  categoriesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: Spacing.xxl},
  categoryCard: {
    width: '48%',
    marginBottom: Spacing.md,
    padding: Spacing.md,
    backgroundColor: Colors.surfaceCard},
  categoryIconWrap: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.primaryGlow,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm},
  categoryIcon: {
    fontSize: 22},
  categoryTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2},
  categoryDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginBottom: Spacing.sm},
  categoryBadge: {
    alignSelf: 'flex-start'},
  stepsCard: {
    padding: Spacing.lg,
    backgroundColor: Colors.surface,
    marginBottom: Spacing.xxl},
  stepItem: {
    flexDirection: 'row',
    alignItems: 'center'},
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md},
  stepNumText: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold,
    fontSize: Typography.sizes.sm},
  stepInfo: {
    flex: 1},
  stepTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2},
  stepDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted},
  stepDivider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
    marginLeft: 40},
  adminCard: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    marginBottom: Spacing.xl},
  adminRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'},
  adminTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight},
  adminSubtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2},
  adminArrow: {
    fontSize: 18,
    color: Colors.primaryLight},
  footerText: {
    textAlign: 'center',
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: Spacing.md}});
