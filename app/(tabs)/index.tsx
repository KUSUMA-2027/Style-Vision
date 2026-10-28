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

import { Colors, Spacing, BorderRadius, Typography, Shadows } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { api, getAuthToken } from '@/services/api';



export default function HomeDashboard() {
  const router = useRouter();
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [isAdmin, setIsAdmin] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const checkHealth = async () => {
    try {
      setBackendStatus('checking');
      await api.health();
      setBackendStatus('connected');
    } catch {
      setBackendStatus('disconnected');
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

        {/* Studio Ready Status Pill */}
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
                  ? 'Styling Studio Ready ✨'
                  : backendStatus === 'checking'
                  ? 'Connecting to studio...'
                  : 'Studio offline • Tap to reconnect'}
              </Text>
            </View>
            <TouchableOpacity onPress={checkHealth}>
              <Text style={styles.refreshText}>↻</Text>
            </TouchableOpacity>
          </View>
        </Card>

        {/* Hero Banner */}
        <Card style={styles.heroCard} variant="elevated">
          <Badge label="VIRTUAL STYLING ATELIER" variant="primary" style={styles.heroBadge} />
          <Text style={styles.heroHeading}>Personalized Virtual Styling</Text>
          <Text style={styles.heroBody}>
            Try on designer outfits, fine jewelry, trending hairstyles,
            and beauty shades directly on your photo with realistic fit and natural lighting.
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
            <Text style={styles.categoryTitle}>Wardrobe & Outfits</Text>
            <Text style={styles.categoryDesc}>Casual, party & daily fashion</Text>
            <Badge label="Virtual Fit" variant="primary" style={styles.categoryBadge} />
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
            <Text style={styles.categoryDesc}>Earrings, necklaces & glasses</Text>
            <Badge label="Smart Fit" variant="success" style={styles.categoryBadge} />
          </Card>

          {/* Makeup */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/makeup')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>💄</Text>
            </View>
            <Text style={styles.categoryTitle}>Beauty & Makeup</Text>
            <Text style={styles.categoryDesc}>Lipsticks, blush & eyeshadow</Text>
            <Badge label="Natural Glam" variant="warning" style={styles.categoryBadge} />
          </Card>

          {/* Hairstyles */}
          <Card
            style={styles.categoryCard}
            onPress={() => router.push('/try-on/hairstyle')}
          >
            <View style={styles.categoryIconWrap}>
              <Text style={styles.categoryIcon}>✂️</Text>
            </View>
            <Text style={styles.categoryTitle}>Hair & Coiffure</Text>
            <Text style={styles.categoryDesc}>Trendy cuts, waves & shades</Text>
            <Badge label="Salon Style" variant="muted" style={styles.categoryBadge} />
          </Card>
        </View>

        {/* How It Works Guide */}
        <Text style={styles.sectionHeading}>How It Works</Text>
        <Card style={styles.stepsCard} variant="outlined">
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>1</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Upload Your Photo</Text>
              <Text style={styles.stepDesc}>Upload a front-facing portrait to start your virtual styling session.</Text>
            </View>
          </View>
          <View style={styles.stepDivider} />
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>2</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Choose Your Styles</Text>
              <Text style={styles.stepDesc}>Browse outfits, jewelry, hair cuts, and makeup shades to try on.</Text>
            </View>
          </View>
          <View style={styles.stepDivider} />
          <View style={styles.stepItem}>
            <View style={styles.stepNumber}><Text style={styles.stepNumText}>3</Text></View>
            <View style={styles.stepInfo}>
              <Text style={styles.stepTitle}>Instant Reveal</Text>
              <Text style={styles.stepDesc}>See your tailored look fitted naturally while preserving your facial identity.</Text>
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
          STYLEVISION · Personal Fashion & Beauty Styling
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
