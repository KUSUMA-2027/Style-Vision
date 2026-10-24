import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { useStylingSession } from '@/services/session';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';


type CategoryKey = 'all' | 'outfit' | 'accessories' | 'makeup' | 'hairstyle';

export default function TryOnHubScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const [selectedFilter, setSelectedFilter] = useState<CategoryKey>('all');

  const handleUndoEverything = () => {
    Alert.alert(
      'Undo Everything?',
      'This will completely delete your model portrait and reset active styling. Your uploaded accessories, dresses, and saved lookbook styles will remain safe. You will be redirected to the home page.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Portrait & Reset',
          style: 'destructive',
          onPress: async () => {
            try {
              await session.undoEverything();
              router.replace('/(tabs)');
            } catch (err: any) {
              Alert.alert('Error', err.message || 'Could not reset session.');
            }
          },
        },
      ]
    );
  };

  const studios = [
    {
      id: 'outfit',
      title: 'Haute Wardrobe Fitting',
      desc: 'Bespoke garment fitting with true collar, shoulder span and posture alignment',
      route: '/try-on/outfit',
      icon: '👗',
      badge: 'Neural Diffusion',
      badgeVariant: 'primary' as const,
      category: 'outfit' as const},
    {
      id: 'accessories',
      title: 'Fine Jewelry & Optics',
      desc: 'Diamond tennis bracelets, aviators, luxury necklaces, rings & handbags',
      route: '/try-on/accessories',
      icon: '💎',
      badge: 'Pose Anchored',
      badgeVariant: 'success' as const,
      category: 'accessories' as const},
    {
      id: 'makeup',
      title: 'Beauty & Makeup Atelier',
      desc: 'Velvet lipsticks, metallic eyeshadow palettes & skin contour blending',
      route: '/try-on/makeup',
      icon: '💄',
      badge: 'Mesh Blend',
      badgeVariant: 'warning' as const,
      category: 'makeup' as const},
    {
      id: 'hairstyle',
      title: 'Haute Coiffure',
      desc: 'Textured beach waves, chic bobs, layered shags & custom color tints',
      route: '/try-on/hairstyle',
      icon: '✂️',
      badge: 'Cranial Pose',
      badgeVariant: 'muted' as const,
      category: 'hairstyle' as const},
  ];

  const filteredStudios =
    selectedFilter === 'all'
      ? studios
      : studios.filter((s) => s.category === selectedFilter);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Atelier Studios</Text>
          <Text style={styles.subtitle}>Select a luxury atelier to curate your bespoke look</Text>
        </View>

        {/* Upload Portrait Card */}
        <Card
          style={styles.uploadCard}
          variant="elevated"
          onPress={() => router.push('/upload')}
        >
          <View style={styles.uploadContent}>
            <View style={styles.uploadIconWrap}>
              <Text style={styles.uploadIcon}>📷</Text>
            </View>
            <View style={styles.uploadTextWrap}>
              <Text style={styles.uploadTitle}>Your Portrait Photograph</Text>
              <Text style={styles.uploadDesc}>
                {session.base
                  ? 'Model portrait loaded ✓. Tap to change or undo below.'
                  : 'Tap here to upload, preview, or change your photo for virtual try-on.'}
              </Text>
            </View>
            <Text style={styles.uploadActionText}>{session.base ? 'Change ➔' : 'Upload ➔'}</Text>
          </View>
          {Boolean(session.base) && (
            <TouchableOpacity
              style={styles.undoCardBtn}
              onPress={(e) => {
                e.stopPropagation();
                handleUndoEverything();
              }}
            >
              <Text style={styles.undoCardBtnText}>🗑️ Undo Everything (Delete Model Portrait)</Text>
            </TouchableOpacity>
          )}
        </Card>

        {/* Complete Look Card */}
        <Card
          style={styles.uploadCard}
          variant="elevated"
          onPress={() => router.push('/complete-look')}
        >
          <View style={styles.uploadContent}>
            <View style={styles.uploadIconWrap}>
              <Text style={styles.uploadIcon}>🪞</Text>
            </View>
            <View style={styles.uploadTextWrap}>
              <Text style={styles.uploadTitle}>The Complete Look</Text>
              <Text style={styles.uploadDesc}>
                View your combined styled look — remove items, save, download, or share.
              </Text>
            </View>
            <Text style={styles.uploadActionText}>Open ➔</Text>
          </View>
        </Card>

        {/* Filter Pills */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {(
            [
              { key: 'all', label: 'All Studios' },
              { key: 'outfit', label: 'Wardrobe' },
              { key: 'accessories', label: 'Jewelry' },
              { key: 'makeup', label: 'Beauty' },
              { key: 'hairstyle', label: 'Coiffure' },
            ] as const
          ).map((item) => {
            const active = selectedFilter === item.key;
            return (
              <TouchableOpacity
                key={item.key}
                onPress={() => setSelectedFilter(item.key)}
                style={[styles.filterPill, active && styles.filterPillActive]}
              >
                <Text
                  style={[styles.filterText, active && styles.filterTextActive]}
                >
                  {item.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Studios List */}
        <View style={styles.studiosList}>
          {filteredStudios.map((studio) => (
            <Card
              key={studio.id}
              style={styles.studioCard}
              onPress={() => router.push(studio.route as any)}
            >
              <View style={styles.studioRow}>
                <View style={styles.studioIconWrap}>
                  <Text style={styles.studioIcon}>{studio.icon}</Text>
                </View>
                <View style={styles.studioInfo}>
                  <View style={styles.studioTitleRow}>
                    <Text style={styles.studioTitle}>{studio.title}</Text>
                  </View>
                  <Text style={styles.studioDesc}>{studio.desc}</Text>
                  <Badge
                    label={studio.badge}
                    variant={studio.badgeVariant}
                    style={styles.studioBadge}
                  />
                </View>
                <Text style={styles.chevron}>→</Text>
              </View>
            </Card>
          ))}
        </View>

        {/* Photography Tips Card */}
        <Card style={styles.tipsCard} variant="outlined">
          <Text style={styles.tipsTitle}>💡 Tips for Best AI Results</Text>
          <Text style={styles.tipText}>• Use natural, front-facing lighting</Text>
          <Text style={styles.tipText}>• Maintain a clear, upright posture</Text>
          <Text style={styles.tipText}>• Plain or uncluttered background recommended</Text>
          <Text style={styles.tipText}>• Avoid heavy shadows covering facial features</Text>
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
  subtitle: {
    fontSize: Typography.sizes.sm,
    color: Colors.textMuted,
    marginTop: 4},
  undoCardBtn: {
    marginTop: Spacing.sm,
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.4)',
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  undoCardBtnText: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: '#EF4444',
  },
  uploadCard: {
    backgroundColor: Colors.surfaceCard,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.borderLight},
  uploadContent: {
    flexDirection: 'row',
    alignItems: 'center'},
  uploadIconWrap: {
    width: 48,
    height: 48,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.primaryGlow,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md},
  uploadIcon: {
    fontSize: 24},
  uploadTextWrap: {
    flex: 1},
  uploadTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2},
  uploadDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    lineHeight: 18},
  uploadActionText: {
    fontSize: Typography.sizes.xs,
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
    marginLeft: Spacing.sm},
  filterRow: {
    flexDirection: 'row',
    marginBottom: Spacing.xl,
    paddingVertical: 2},
  filterPill: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    marginRight: Spacing.sm},
  filterPillActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary},
  filterText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium},
  filterTextActive: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold},
  studiosList: {
    marginBottom: Spacing.xl},
  studioCard: {
    backgroundColor: Colors.surfaceCard,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border},
  studioRow: {
    flexDirection: 'row',
    alignItems: 'center'},
  studioIconWrap: {
    width: 48,
    height: 48,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.md},
  studioIcon: {
    fontSize: 24},
  studioInfo: {
    flex: 1},
  studioTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2},
  studioTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary},
  studioDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginBottom: Spacing.sm,
    lineHeight: 16},
  studioBadge: {
    alignSelf: 'flex-start'},
  chevron: {
    fontSize: 20,
    color: Colors.primaryLight,
    marginLeft: Spacing.sm},
  tipsCard: {
    padding: Spacing.lg,
    backgroundColor: Colors.surface},
  tipsTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.warning,
    marginBottom: Spacing.sm},
  tipText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    lineHeight: 20}});
