import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator,
  RefreshControl} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import { getApiBaseUrl, api } from '@/services/api';

interface HistoryItem {
  look_id: string;
  title: string;
  category: 'outfit' | 'accessories' | 'makeup' | 'hairstyle' | 'complete';
  categoryLabel: string;
  createdAt: string;
  styleName: string;
  originalImage: string | null;
  resultImage: string | null;
}

const CATEGORY_LABEL: Record<string, string> = {
  outfit: 'Outfit Try-On',
  accessories: 'Accessories',
  makeup: 'Makeup',
  hairstyle: 'Hairstyle',
  complete: 'Complete Look',
};

function formatTime(iso: string | Date): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  const date = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return `${date}, ${time}`;
}

export default function HistoryScreen() {
  const router = useRouter();
  const baseUrl = getApiBaseUrl();
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'outfit' | 'accessories' | 'makeup' | 'hairstyle' | 'complete'>('all');
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await api.history.list();
      const looks = (res.looks ?? []).map((l: any) => ({
        look_id: l.look_id,
        title: l.title ?? 'Untitled Look',
        category: l.category ?? 'outfit',
        categoryLabel: CATEGORY_LABEL[l.category] ?? 'Look',
        createdAt: formatTime(l.created_at),
        styleName: l.style_item_name ?? 'Custom Style',
        originalImage: l.original_image_url || null,
        resultImage: l.result_image_url || null,
      }));
      setItems(looks);
    } catch (err: any) {
      setError(err.message || 'Could not load your lookbook.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Reload every time the tab is focused so newly saved looks appear
  useFocusEffect(
    useCallback(() => {
      loadHistory();
    }, [loadHistory])
  );

  const handleDelete = (id: string, title: string) => {
    Alert.alert('Remove Look', `Are you sure you want to remove "${title}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.history.delete(id);
            setItems((prev) => prev.filter((item) => item.look_id !== id));
          } catch (err: any) {
            Alert.alert('Delete Failed', err.message || 'Could not remove this look.');
          }
        }},
    ]);
  };

  const resolveUrl = (url: string | null) =>
    url ? (url.startsWith('http') ? url : `${baseUrl}${url}`) : null;

  const filteredItems =
    selectedFilter === 'all'
      ? items
      : items.filter((item) => item.category === selectedFilter);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Atelier Lookbook</Text>
          <Text style={styles.subtitle}>
            Curated haute couture creations & fitting archive
          </Text>
        </View>

        {/* Filter Pills */}
        <View style={styles.filterContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterRow}
          >
            {(
              [
                { key: 'all', label: 'All' },
                { key: 'outfit', label: 'Outfits' },
                { key: 'accessories', label: 'Accessories' },
                { key: 'makeup', label: 'Makeup' },
                { key: 'hairstyle', label: 'Hairstyles' },
                { key: 'complete', label: 'Complete Looks' },
              ] as const
            ).map((f) => {
              const active = selectedFilter === f.key;
              return (
                <TouchableOpacity
                  key={f.key}
                  onPress={() => setSelectedFilter(f.key)}
                  style={[styles.filterPill, active && styles.filterPillActive]}
                >
                  <Text
                    style={[styles.filterText, active && styles.filterTextActive]}
                  >
                    {f.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Content list, loading, error, or empty state */}
        {loading ? (
          <View style={styles.centerWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Loading your lookbook...</Text>
          </View>
        ) : error && items.length === 0 ? (
          <EmptyState
            icon="⚠️"
            title="Could Not Load Lookbook"
            description={error}
            actionTitle="Retry"
            onAction={() => loadHistory()}
          />
        ) : filteredItems.length === 0 ? (
          <EmptyState
            icon="💜"
            title="No Saved Looks Yet"
            description="Experiment with virtual try-ons and save your favorite results to build your personalized style lookbook."
            actionTitle="Explore Try-On"
            onAction={() => router.push('/(tabs)/try-on')}
          />
        ) : (
          <ScrollView
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={() => loadHistory(true)}
                tintColor={Colors.primary}
              />
            }
          >
            {filteredItems.map((item) => {
              const originalUri = resolveUrl(item.originalImage);
              const resultUri = resolveUrl(item.resultImage);
              return (
                <Card key={item.look_id} style={styles.card} variant="elevated">
                  <View style={styles.cardHeader}>
                    <Badge
                      label={item.categoryLabel}
                      variant={
                        item.category === 'outfit'
                          ? 'primary'
                          : item.category === 'accessories'
                          ? 'success'
                          : item.category === 'makeup'
                          ? 'warning'
                          : 'muted'
                      }
                    />
                    <Text style={styles.timeText}>{item.createdAt}</Text>
                  </View>

                  {/* Real before/after previews */}
                  <View style={styles.previewRow}>
                    <View style={styles.previewBox}>
                      {originalUri ? (
                        <Image source={{ uri: originalUri }} style={styles.previewImage} resizeMode="cover" />
                      ) : (
                        <Text style={styles.previewIcon}>👤</Text>
                      )}
                      <Text style={styles.previewOverlayLabel}>ORIGINAL</Text>
                    </View>
                    <Text style={styles.previewArrow}>⇄</Text>
                    <View style={[styles.previewBox, styles.previewBoxResult]}>
                      {resultUri ? (
                        <Image source={{ uri: resultUri }} style={styles.previewImage} resizeMode="cover" />
                      ) : (
                        <Text style={styles.previewIcon}>✨</Text>
                      )}
                      <Text style={styles.previewOverlayLabel}>STYLED</Text>
                    </View>
                  </View>

                  <Text style={styles.cardTitle}>{item.title}</Text>
                  <Text style={styles.cardStyleName}>Item: {item.styleName}</Text>

                  <View style={styles.cardActions}>
                    <Button
                      title="Compare Before & After"
                      variant="secondary"
                      size="sm"
                      onPress={() =>
                        router.push({
                          pathname: '/result',
                          params: {
                            title: item.title,
                            style: item.styleName,
                            category: item.category,
                            resultUrl: item.resultImage ?? '',
                            originalUrl: item.originalImage ?? '',
                          }})
                      }
                      style={styles.actionButton}
                    />
                    <TouchableOpacity
                      onPress={() => handleDelete(item.look_id, item.title)}
                      style={styles.deleteButton}
                      accessibilityLabel="Delete Look"
                    >
                      <Text style={styles.deleteIcon}>🗑️</Text>
                    </TouchableOpacity>
                  </View>
                </Card>
              );
            })}
          </ScrollView>
        )}
      </View>
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
  header: {
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm},
  title: {
    fontSize: Typography.sizes.xxl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary},
  subtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2},
  centerWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl},
  loadingText: {
    marginTop: Spacing.md,
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted},
  filterContainer: {
    paddingVertical: Spacing.sm},
  filterRow: {
    paddingHorizontal: Spacing.xl},
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
    color: Colors.textInverse,
    fontWeight: Typography.weights.bold},
  listContent: {
    padding: Spacing.xl,
    paddingBottom: Spacing.xxxl * 2},
  card: {
    marginBottom: Spacing.lg,
    backgroundColor: Colors.surfaceCard,
    borderWidth: 1,
    borderColor: Colors.border},
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md},
  timeText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted},
  previewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: Spacing.sm,
    gap: Spacing.md},
  previewBox: {
    flex: 1,
    height: 110,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden'},
  previewBoxResult: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primaryGlow},
  previewImage: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%'},
  previewOverlayLabel: {
    position: 'absolute',
    bottom: 4,
    alignSelf: 'center',
    fontSize: 8,
    color: Colors.textPrimary,
    letterSpacing: 1,
    fontWeight: Typography.weights.bold,
    backgroundColor: 'rgba(0,0,0,0.55)',
    overflow: 'hidden',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6},
  previewIcon: {
    fontSize: 28},
  previewArrow: {
    fontSize: 18,
    color: Colors.primaryLight},
  cardTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginTop: Spacing.sm},
  cardStyleName: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    marginBottom: Spacing.md,
    marginTop: 2},
  cardActions: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'},
  actionButton: {
    flex: 1,
    marginRight: Spacing.md},
  deleteButton: {
    padding: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border},
  deleteIcon: {
    fontSize: 16}});
