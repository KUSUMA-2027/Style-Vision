import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { getApiBaseUrl, api } from '@/services/api';
import { useStylingSession } from '@/services/session';

interface StyleItem {
  item_id: string;
  name: string;
  category: string;
  subcategory?: string;
  description?: string;
  color?: string;
  tags: string[];
}

export default function MakeupStudioScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const baseUrl = getApiBaseUrl();
  const [items, setItems] = useState<StyleItem[]>([]);
  const [latestPortrait, setLatestPortrait] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'lipstick' | 'eyeshadow' | 'blush'>('lipstick');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [finish, setFinish] = useState<'matte' | 'satin' | 'glossy'>('satin');
  const [intensity, setIntensity] = useState<number>(60);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [catData, portraitData] = await Promise.all([
        api.catalogue.list('makeup'),
        api.upload.getLatest().catch(() => null),
      ]);
      setItems(catData.items ?? []);
      if (portraitData) {
        setLatestPortrait(portraitData);
        session.ensureSession({ image_id: portraitData.image_id, url: portraitData.url });
      }
      const defaultItem = catData.items?.find((i: StyleItem) => i.subcategory === 'lipstick') ?? catData.items?.[0];
      if (defaultItem) setSelectedId(defaultItem.item_id);
    } catch (err: any) {
      setError(err.message || 'Could not load makeup catalogue.');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadData();
  }, [loadData]);

  const currentShades = items.filter((s) => s.subcategory === activeTab);

  // Effective source image: latest chained result if a styling session is active
  const sourceImage = session.current ??
    (latestPortrait ? { image_id: latestPortrait.image_id, url: latestPortrait.url } : null);
  const appliedStageCount = Object.keys(session.stages).length;
  const isChainedSource = Boolean(session.current && session.stages.makeup?.resultImageId !== session.current.image_id);

  const handleApply = async () => {
    if (!selectedId) {
      Alert.alert('Select a Shade', 'Please select a makeup shade to apply.');
      return;
    }
    if (!sourceImage) {
      Alert.alert('Portrait Required', 'Please upload your portrait photo first.');
      return;
    }
    const chosen = items.find((s) => s.item_id === selectedId);
    const chosenColor = chosen?.color ?? '#BA000D';
    setIsProcessing(true);
    try {
      const personId = sourceImage.image_id;
      const res = await api.tryon.makeup(
        personId,
        activeTab,
        chosenColor,
        intensity / 100,
        finish
      );

      if (res.status === 'failed') {
        Alert.alert('Makeup Application Failed', res.error || 'No face could be detected in the current image. Please use a clear, front-facing photo.');
        return;
      }

      session.setSelection('makeup', { itemId: selectedId, name: chosen?.name, type: activeTab });
      session.applyStageResult({
        stage: 'makeup',
        tryonId: res.tryon_id,
        resultImageId: res.result_image_id ?? null,
        resultUrl: res.result_image_url ?? '',
        sourceUrl: res.original_image_url ?? sourceImage.url,
        title: chosen?.name ?? 'Virtual Makeup Look',
        style: `${activeTab} • ${finish}`,
        slot: activeTab,
        closeupResultUrl: res.closeup_result_image_url ?? null,
        closeupOriginalUrl: res.closeup_original_image_url ?? null,
        appliedAt: Date.now(),
      });

      router.push({
        pathname: '/result',
        params: {
          category: 'makeup',
          title: chosen?.name ?? 'Virtual Makeup Look',
          style: `${activeTab.toUpperCase()} • ${finish.toUpperCase()} • ${intensity}% Intensity`,
          itemId: selectedId,
          tryonId: res.tryon_id,
          resultUrl: res.result_image_url,
          originalUrl: res.original_image_url,
          closeupResultUrl: res.closeup_result_image_url || '',
          closeupOriginalUrl: res.closeup_original_image_url || '',
          mode: 'local',
        },
      });
    } catch (err: any) {
      Alert.alert('Try-On Error', err.message || 'Could not process makeup blending.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Engine Banner */}
        <Card style={styles.engineCard} variant="flat">
          <View style={styles.engineRow}>
            <Text style={styles.engineIcon}>🎨</Text>
            <View style={styles.engineInfo}>
              <Text style={styles.engineTitle}>Facial Landmark Alpha-Blending</Text>
              <Text style={styles.engineDesc}>
                OpenCV + MediaPipe: Lip perimeter and eye orbit landmark color tinting
              </Text>
            </View>
            <Badge label="CPU Live" variant="warning" />
          </View>
        </Card>

        {/* Photo prompt / Active Portrait */}
        <Text style={styles.sectionHeading}>1. Your Portrait</Text>
        <TouchableOpacity style={styles.photoCard} onPress={() => router.push('/upload')} activeOpacity={0.8}>
          {sourceImage ? (
            <View style={styles.portraitRow}>
              <Image
                source={{
                  uri: sourceImage.url.startsWith('http')
                    ? sourceImage.url
                    : `${baseUrl}${sourceImage.url}`,
                }}
                style={styles.portraitThumb}
              />
              <View style={styles.photoTextWrap}>
                <View style={styles.validatedBadgeRow}>
                  <Text style={styles.photoTitle}>
                    {isChainedSource ? 'Styled Look Active' : 'Portrait Active'}
                  </Text>
                  <Badge
                    label={isChainedSource ? `${appliedStageCount} Stage${appliedStageCount > 1 ? 's' : ''} Applied` : 'Face Landmarks'}
                    variant={isChainedSource ? 'primary' : 'success'}
                  />
                </View>
                <Text style={styles.photoDesc}>
                  {isChainedSource
                    ? 'Makeup will be applied over your latest styled result — outfit and accessories preserved.'
                    : 'Tap to change or take a new portrait'}
                </Text>
              </View>
              <Text style={styles.photoChevron}>🔄</Text>
            </View>
          ) : (
            <View style={styles.portraitRow}>
              <Text style={styles.photoIcon}>📷</Text>
              <View style={styles.photoTextWrap}>
                <Text style={styles.photoTitle}>Tap to upload your portrait</Text>
                <Text style={styles.photoDesc}>Even lighting on face allows accurate lip & eye mesh mapping.</Text>
              </View>
              <Text style={styles.photoChevron}>→</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Studio Product Switcher */}
        <Text style={styles.sectionHeading}>2. Choose Product</Text>
        <View style={styles.tabBar}>
          {(['lipstick', 'eyeshadow', 'blush'] as const).map((tab) => {
            const active = activeTab === tab;
            return (
              <TouchableOpacity
                key={tab}
                onPress={() => {
                  setActiveTab(tab);
                  const firstOfTab = items.find((s) => s.subcategory === tab);
                  if (firstOfTab) setSelectedId(firstOfTab.item_id);
                }}
                style={[styles.tabBtn, active && styles.tabBtnActive]}
              >
                <Text style={[styles.tabText, active && styles.tabTextActive]}>
                  {tab === 'lipstick' ? '💄 Lipstick' : tab === 'eyeshadow' ? '👁️ Eyeshadow' : '🌸 Blush'}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Catalogue States */}
        {loading && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Loading makeup shades...</Text>
          </View>
        )}

        {!loading && error && (
          <ErrorMessage message={error} onRetry={loadData} />
        )}

        {!loading && !error && currentShades.length === 0 && (
          <View style={styles.emptyWrap}>
            <Text style={styles.emptyIcon}>💄</Text>
            <Text style={styles.emptyText}>No shades found in this category.</Text>
          </View>
        )}

        {/* Color Swatches Grid */}
        {!loading && !error && currentShades.length > 0 && (
          <View style={styles.swatchesGrid}>
            {currentShades.map((shade) => {
              const isSelected = selectedId === shade.item_id;
              const colorHex = shade.color ?? '#BA000D';
              return (
                <TouchableOpacity
                  key={shade.item_id}
                  activeOpacity={0.8}
                  onPress={() => setSelectedId(shade.item_id)}
                  style={[
                    styles.swatchCard,
                    isSelected && styles.swatchCardSelected,
                  ]}
                >
                  <View style={[styles.colorCircle, { backgroundColor: colorHex }]} />
                  <Text style={styles.shadeName} numberOfLines={1}>
                    {shade.name}
                  </Text>
                  <Text style={styles.shadeHex}>{colorHex}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Finish Selector */}
        <Text style={styles.sectionHeading}>3. Finish & Texture</Text>
        <View style={styles.finishRow}>
          {(['matte', 'satin', 'glossy'] as const).map((f) => {
            const active = finish === f;
            return (
              <TouchableOpacity
                key={f}
                onPress={() => setFinish(f)}
                style={[styles.finishBtn, active && styles.finishBtnActive]}
              >
                <Text style={[styles.finishText, active && styles.finishTextActive]}>
                  {f.toUpperCase()}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Intensity Level */}
        <Text style={styles.sectionHeading}>4. Blend Intensity: {intensity}%</Text>
        <View style={styles.intensityRow}>
          {[30, 60, 90].map((level) => {
            const active = intensity === level;
            return (
              <TouchableOpacity
                key={level}
                onPress={() => setIntensity(level)}
                style={[styles.intensityBtn, active && styles.intensityBtnActive]}
              >
                <Text style={[styles.intensityText, active && styles.intensityTextActive]}>
                  {level === 30 ? 'Soft (30%)' : level === 60 ? 'Medium (60%)' : 'Bold (90%)'}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Apply Makeup Button */}
        <Button
          title={isProcessing ? 'Blending Makeup Effect...' : 'Apply Makeup Look 💄'}
          variant="primary"
          size="lg"
          loading={isProcessing}
          disabled={!selectedId || loading}
          onPress={handleApply}
          style={styles.applyButton}
        />
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
  engineCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border},
  engineRow: {
    flexDirection: 'row',
    alignItems: 'center'},
  engineIcon: {
    fontSize: 24,
    marginRight: Spacing.md},
  engineInfo: {
    flex: 1},
  engineTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary},
  engineDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2},
  photoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primaryGlow,
    borderStyle: 'dashed',
    padding: Spacing.md,
    marginBottom: Spacing.xl},
  portraitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md},
  portraitThumb: {
    width: 52,
    height: 52,
    borderRadius: BorderRadius.md,
    borderWidth: 1.5,
    borderColor: Colors.primary},
  validatedBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: 2},
  photoIcon: { fontSize: 28, marginRight: Spacing.md },
  photoTextWrap: { flex: 1 },
  photoTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight},
  photoDesc: { fontSize: Typography.sizes.xs, color: Colors.textMuted, marginTop: 2 },
  photoChevron: { fontSize: 20, color: Colors.primaryLight },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: 4,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border},
  tabBtn: {
    flex: 1,
    paddingVertical: Spacing.sm + 2,
    alignItems: 'center',
    borderRadius: BorderRadius.md},
  tabBtnActive: {
    backgroundColor: Colors.primary},
  tabText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium},
  tabTextActive: {
    color: Colors.textInverse,
    fontWeight: Typography.weights.bold},
  sectionHeading: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.5},
  loadingWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  loadingText: { color: Colors.textMuted, fontSize: Typography.sizes.xs, marginTop: Spacing.sm },
  emptyWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  emptyIcon: { fontSize: 40, marginBottom: Spacing.sm },
  emptyText: { color: Colors.textMuted, fontSize: Typography.sizes.sm },
  swatchesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: Spacing.xl},
  swatchCard: {
    width: '48%',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.border,
    alignItems: 'center'},
  swatchCardSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primaryGlow},
  colorCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    marginBottom: Spacing.sm,
    borderWidth: 2,
    borderColor: '#FFFFFF33'},
  shadeName: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary},
  shadeHex: {
    fontSize: 10,
    color: Colors.textMuted,
    marginTop: 2},
  finishRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.xl},
  finishBtn: {
    flex: 1,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center'},
  finishBtnActive: {
    backgroundColor: Colors.primaryGlow,
    borderColor: Colors.primary},
  finishText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.bold},
  finishTextActive: {
    color: Colors.primaryLight},
  intensityRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.xxl},
  intensityBtn: {
    flex: 1,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center'},
  intensityBtnActive: {
    backgroundColor: Colors.primaryGlow,
    borderColor: Colors.primary},
  intensityText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium},
  intensityTextActive: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold},
  applyButton: {
    marginTop: Spacing.sm}});
