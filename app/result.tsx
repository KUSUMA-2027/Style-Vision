import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Image,
  Modal,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as FileSystem from 'expo-file-system/legacy';
import * as MediaLibrary from 'expo-media-library';
import * as Sharing from 'expo-sharing';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { getApiBaseUrl, api } from '@/services/api';
import {
  useStylingSession,
  STAGE_ORDER,
  STAGE_LABEL,
  NEXT_STAGE_ROUTE,
  type Stage,
} from '@/services/session';

export default function ResultScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const params = useLocalSearchParams<{
    category?: string;
    title?: string;
    style?: string;
    resultUrl?: string;
    originalUrl?: string;
    closeupResultUrl?: string;
    closeupOriginalUrl?: string;
    itemId?: string;
    tryonId?: string;
    mode?: string;
  }>();

  const [viewMode, setViewMode] = useState<'split' | 'before' | 'after'>('split');
  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);

  const hasCloseup = Boolean(params.closeupResultUrl);
  const [focusMode, setFocusMode] = useState<'closeup' | 'full'>(
    hasCloseup ? 'closeup' : 'full'
  );
  const [zoomModalVisible, setZoomModalVisible] = useState(false);
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);

  const lookTitle = params.title || 'Virtual Styling Result';
  const lookCategory = params.category || 'outfit';
  const lookStyle = params.style || 'Custom Style';

  // Which stage of the pipeline is this result? (drives progress bar + continue flow)
  const currentStage = (STAGE_ORDER as readonly string[]).includes(lookCategory)
    ? (lookCategory as Stage)
    : 'outfit';
  const nextStage: Stage | null = (() => {
    const idx = STAGE_ORDER.indexOf(currentStage);
    return STAGE_ORDER.slice(idx + 1).find((s) => !session.stages[s]) ?? null;
  })();
  const continueRoute = nextStage ? NEXT_STAGE_ROUTE[nextStage] : '/complete-look';
  const continueLabel = nextStage ? `Continue to ${STAGE_LABEL[nextStage]}` : 'View Complete Look';
  const allStagesDone = STAGE_ORDER.every((s) => Boolean(session.stages[s]));
  const isChainedResult = Boolean(
    session.base &&
      params.originalUrl &&
      !params.originalUrl.endsWith(session.base.url)
  );

  const baseUrl = getApiBaseUrl();
  const fullResultUrl = params.resultUrl
    ? params.resultUrl.startsWith('http')
      ? params.resultUrl
      : `${baseUrl}${params.resultUrl}`
    : null;

  const fullOriginalUrl = params.originalUrl
    ? params.originalUrl.startsWith('http')
      ? params.originalUrl
      : `${baseUrl}${params.originalUrl}`
    : null;

  const activeResultUrl =
    focusMode === 'closeup' && params.closeupResultUrl
      ? (params.closeupResultUrl.startsWith('http') ? params.closeupResultUrl : `${baseUrl}${params.closeupResultUrl}`)
      : fullResultUrl;

  const activeOriginalUrl =
    focusMode === 'closeup' && params.closeupOriginalUrl
      ? (params.closeupOriginalUrl.startsWith('http') ? params.closeupOriginalUrl : `${baseUrl}${params.closeupOriginalUrl}`)
      : fullOriginalUrl;

  const openZoom = (url: string | null) => {
    if (url) {
      setZoomImageUrl(url);
      setZoomModalVisible(true);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const tryonIdToSave = params.tryonId || `tryon-outfit-${Date.now()}`;
      // Include full session chain metadata so the look can be reproduced later
      const stageMeta = STAGE_ORDER.filter((s) => session.stages[s]).map((s) => ({
        stage: s,
        tryon_id: session.stages[s]!.tryonId,
        result_image_id: session.stages[s]!.resultImageId,
        result_image_url: session.stages[s]!.resultUrl,
        title: session.stages[s]!.title,
      }));
      await api.history.save(tryonIdToSave, lookTitle, {
        base_image_id: session.base?.image_id,
        final_image_id: session.current?.image_id,
        stages: stageMeta,
      });
      setIsSaved(true);
      Alert.alert('Saved to Lookbook! 💎', 'This couture styling result has been saved to your Atelier Lookbook.');
    } catch (err: any) {
      Alert.alert('Save Notice', err.message || 'Could not save this look right now.');
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    if (!fullResultUrl) return;
    setDownloading(true);
    try {
      if (Platform.OS === 'web') {
        window.open(fullResultUrl, '_blank');
        return;
      }
      const perm = await MediaLibrary.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert('Permission Needed', 'Please allow photo library access to download your look.');
        return;
      }
      const download = await FileSystem.downloadAsync(
        fullResultUrl,
        `${FileSystem.cacheDirectory}${params.tryonId || 'stylevision-look'}.png`
      );
      await MediaLibrary.saveToLibraryAsync(download.uri);
      Alert.alert('Downloaded! 📥', 'Your complete look has been saved to your photo library.');
    } catch (err: any) {
      Alert.alert('Download Failed', err.message || 'Could not download the image right now.');
    } finally {
      setDownloading(false);
    }
  };

  const handleShare = async () => {
    if (!fullResultUrl) return;
    try {
      if (Platform.OS === 'web') {
        window.open(fullResultUrl, '_blank');
        return;
      }
      if (await Sharing.isAvailableAsync()) {
        const download = await FileSystem.downloadAsync(
          fullResultUrl,
          `${FileSystem.cacheDirectory}${params.tryonId || 'stylevision-look'}.png`
        );
        await Sharing.shareAsync(download.uri, { mimeType: 'image/png' });
      }
    } catch (err: any) {
      Alert.alert('Share Failed', err.message || 'Could not share the image right now.');
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Title Header */}
        <View style={styles.header}>
          <Badge
            label={lookCategory.toUpperCase()}
            variant={
              lookCategory === 'outfit'
                ? 'primary'
                : lookCategory === 'accessories'
                ? 'success'
                : lookCategory === 'makeup'
                ? 'warning'
                : 'muted'
            }
            style={styles.badge}
          />
          <Text style={styles.title}>{lookTitle}</Text>
          <Text style={styles.subtitle}>{lookStyle}</Text>
        </View>

        {/* Styling Progress: Outfit → Accessories → Makeup → Hairstyle → Complete Look */}
        <View style={styles.progressRow}>
          {STAGE_ORDER.map((stage, i) => {
            const done = Boolean(session.stages[stage]);
            const active = stage === currentStage;
            return (
              <View key={stage} style={styles.progressStepWrap}>
                <View style={[styles.progressDot, done && styles.progressDotDone, active && styles.progressDotActive]}>
                  <Text style={[styles.progressDotText, (done || active) && styles.progressDotTextActive]}>
                    {done ? '✓' : i + 1}
                  </Text>
                </View>
                <Text style={[styles.progressLabel, (done || active) && styles.progressLabelActive]}>
                  {STAGE_LABEL[stage]}
                </Text>
              </View>
            );
          })}
          <View style={styles.progressStepWrap}>
            <View style={[styles.progressDot, allStagesDone && styles.progressDotDone]}>
              <Text style={[styles.progressDotText, allStagesDone && styles.progressDotTextActive]}>★</Text>
            </View>
            <Text style={[styles.progressLabel, allStagesDone && styles.progressLabelActive]}>Complete</Text>
          </View>
        </View>
        {isChainedResult && (
          <Text style={styles.chainNote}>
            🔗 Applied on top of your previous stages — your earlier styling is preserved.
          </Text>
        )}

        {/* Focus Mode Bar (Close-Up vs Full Body for Accessories) */}
        {hasCloseup && (
          <View style={styles.focusBar}>
            <TouchableOpacity
              style={[styles.focusBtn, focusMode === 'closeup' && styles.focusBtnActive]}
              onPress={() => setFocusMode('closeup')}
            >
              <Text style={[styles.focusText, focusMode === 'closeup' && styles.focusTextActive]}>
                🔍 Close-Up (Face & Jewelry)
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.focusBtn, focusMode === 'full' && styles.focusBtnActive]}
              onPress={() => setFocusMode('full')}
            >
              <Text style={[styles.focusText, focusMode === 'full' && styles.focusTextActive]}>
                👤 Full-Body View
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {/* View Mode Switcher */}
        <View style={styles.viewModeBar}>
          {(
            [
              { key: 'split', label: 'Side-by-Side' },
              { key: 'before', label: 'Original' },
              { key: 'after', label: 'Virtual Try-On' },
            ] as const
          ).map((mode) => {
            const active = viewMode === mode.key;
            return (
              <TouchableOpacity
                key={mode.key}
                onPress={() => setViewMode(mode.key)}
                style={[styles.modeBtn, active && styles.modeBtnActive]}
              >
                <Text style={[styles.modeText, active && styles.modeTextActive]}>
                  {mode.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Before / After Preview Area */}
        <Card style={styles.previewContainer} variant="elevated">
          <View style={styles.zoomHintRow}>
            <Text style={styles.zoomHintText}>🔍 Tap any image to inspect in full zoom</Text>
          </View>
          {viewMode === 'split' ? (
            <View style={styles.splitRow}>
              {/* Before Column */}
              <TouchableOpacity
                style={styles.splitCol}
                activeOpacity={0.85}
                onPress={() => openZoom(activeOriginalUrl)}
              >
                {activeOriginalUrl ? (
                  <Image source={{ uri: activeOriginalUrl }} style={styles.imagePreview} resizeMode="cover" />
                ) : (
                  <View style={styles.imagePlaceholder}>
                    <Text style={styles.imageEmoji}>👤</Text>
                    <Text style={styles.imageTag}>ORIGINAL</Text>
                  </View>
                )}
                <Text style={styles.colLabel}>Before</Text>
              </TouchableOpacity>

              <View style={styles.dividerCol}>
                <Text style={styles.dividerIcon}>VS</Text>
              </View>

              {/* After Column */}
              <TouchableOpacity
                style={styles.splitCol}
                activeOpacity={0.85}
                onPress={() => openZoom(activeResultUrl)}
              >
                {activeResultUrl ? (
                  <Image source={{ uri: activeResultUrl }} style={styles.imagePreview} resizeMode="cover" />
                ) : (
                  <View style={[styles.imagePlaceholder, styles.styledPlaceholder]}>
                    <Text style={styles.imageEmoji}>✨</Text>
                    <Text style={[styles.imageTag, styles.styledTag]}>TRY-ON</Text>
                  </View>
                )}
                <Text style={styles.colLabel}>After Result</Text>
              </TouchableOpacity>
            </View>
          ) : viewMode === 'before' ? (
            <TouchableOpacity
              style={styles.singleView}
              activeOpacity={0.85}
              onPress={() => openZoom(activeOriginalUrl)}
            >
              {activeOriginalUrl ? (
                <Image source={{ uri: activeOriginalUrl }} style={styles.singleImagePreview} resizeMode="contain" />
              ) : (
                <View style={styles.singleImage}>
                  <Text style={styles.singleEmoji}>👤</Text>
                  <Text style={styles.imageTag}>ORIGINAL PHOTO</Text>
                </View>
              )}
              <Text style={styles.colLabel}>Unedited Portrait</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={styles.singleView}
              activeOpacity={0.85}
              onPress={() => openZoom(activeResultUrl)}
            >
              {activeResultUrl ? (
                <Image source={{ uri: activeResultUrl }} style={styles.singleImagePreview} resizeMode="contain" />
              ) : (
                <View style={[styles.singleImage, styles.styledPlaceholder]}>
                  <Text style={styles.singleEmoji}>✨</Text>
                  <Text style={[styles.imageTag, styles.styledTag]}>AI SYNTHESIZED</Text>
                </View>
              )}
              <Text style={styles.colLabel}>Virtual Style Result</Text>
            </TouchableOpacity>
          )}
        </Card>

        {/* Technical Inference Metrics */}
        <Card style={styles.metricsCard} variant="outlined">
          <Text style={styles.metricsHeading}>🔬 AI Processing Breakdown</Text>
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>Engine Architecture</Text>
            <Text style={styles.metricValue}>
              {lookCategory === 'outfit'
                ? 'CatVTON Diffusion Warp'
                : lookCategory === 'makeup'
                ? 'MediaPipe Face Mesh + Alpha Blend'
                : lookCategory === 'accessories'
                ? 'MediaPipe Face Mesh & Affine Warping'
                : 'MediaPipe Pose Landmark Alignment'}
            </Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>Processing Mode</Text>
            <Text style={styles.metricValue}>
              {params.mode === 'catvton'
                ? 'CatVTON Neural Diffusion (Cloud GPU)'
                : lookCategory === 'accessories'
                ? 'MediaPipe Real-Time CV (Local CPU)'
                : 'Local CPU Prototype Overlay'}
            </Text>
          </View>
          <View style={styles.metricDivider} />
          <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>Output Resolution</Text>
            <Text style={styles.metricValue}>600 × 800 (HD Portrait)</Text>
          </View>
        </Card>

        {/* Action Buttons */}
        <View style={styles.actions}>
          <Button
            title={continueLabel + ' →'}
            variant="primary"
            size="lg"
            onPress={() => router.push(continueRoute as any)}
            style={styles.actionBtn}
          />
          <Button
            title={isSaved ? 'Saved in Looks! ✓' : saving ? 'Saving...' : 'Save to Lookbook 💜'}
            variant={isSaved ? 'secondary' : 'outline'}
            size="md"
            onPress={handleSave}
            disabled={isSaved || saving}
            loading={saving}
            style={styles.actionBtn}
          />
          <View style={styles.downloadRow}>
            <Button
              title={downloading ? 'Downloading...' : 'Download 📥'}
              variant="secondary"
              size="sm"
              onPress={handleDownload}
              disabled={downloading}
              loading={downloading}
              style={styles.downloadBtn}
            />
            <Button
              title="Share"
              variant="secondary"
              size="sm"
              onPress={handleShare}
              style={styles.downloadBtn}
            />
          </View>
        </View>
      </ScrollView>

      {/* Full-screen Zoom Modal */}
      <Modal visible={zoomModalVisible} transparent animationType="fade">
        <View style={styles.zoomModalOverlay}>
          <SafeAreaView style={styles.zoomModalSafe}>
            <View style={styles.zoomModalHeader}>
              <Text style={styles.zoomModalTitle}>High-Resolution Zoom</Text>
              <TouchableOpacity
                style={styles.zoomCloseBtn}
                onPress={() => setZoomModalVisible(false)}
              >
                <Text style={styles.zoomCloseText}>✕ Close</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.zoomImageContainer}>
              {zoomImageUrl ? (
                <Image
                  source={{ uri: zoomImageUrl }}
                  style={styles.zoomModalImage}
                  resizeMode="contain"
                />
              ) : null}
            </View>
          </SafeAreaView>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: Spacing.xl,
    paddingBottom: Spacing.xxxl * 2,
  },
  header: {
    marginBottom: Spacing.lg,
  },
  badge: {
    marginBottom: Spacing.sm,
  },
  title: {
    fontSize: Typography.sizes.xl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
  },
  subtitle: {
    fontSize: Typography.sizes.sm,
    color: Colors.textMuted,
    marginTop: 2,
  },
  viewModeBar: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: 4,
    marginBottom: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modeBtn: {
    flex: 1,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
    borderRadius: BorderRadius.md,
  },
  modeBtnActive: {
    backgroundColor: Colors.primary,
  },
  modeText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  modeTextActive: {
    color: Colors.textInverse,
    fontWeight: Typography.weights.bold,
  },
  previewContainer: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.lg,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  splitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  splitCol: {
    flex: 1,
    alignItems: 'center',
  },
  dividerCol: {
    paddingHorizontal: Spacing.sm,
  },
  dividerIcon: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
  },
  imagePreview: {
    width: '100%',
    height: 220,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
  },
  singleImagePreview: {
    width: '100%',
    height: 340,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surface,
  },
  imagePlaceholder: {
    width: '100%',
    height: 220,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  styledPlaceholder: {
    borderColor: Colors.primary,
    backgroundColor: Colors.surfaceHover,
  },
  imageEmoji: {
    fontSize: 44,
    marginBottom: Spacing.sm,
  },
  imageTag: {
    fontSize: 9,
    fontWeight: Typography.weights.heavy,
    color: Colors.textMuted,
    letterSpacing: 1,
  },
  styledTag: {
    color: Colors.primaryLight,
  },
  colLabel: {
    marginTop: Spacing.sm,
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    fontWeight: Typography.weights.bold,
  },
  singleView: {
    alignItems: 'center',
    width: '100%',
  },
  singleImage: {
    width: '100%',
    height: 340,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  singleEmoji: {
    fontSize: 64,
    marginBottom: Spacing.md,
  },
  metricsCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.lg,
    marginBottom: Spacing.xxl,
  },
  metricsHeading: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: Spacing.md,
  },
  metricRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  metricLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
  },
  metricValue: {
    fontSize: Typography.sizes.xs,
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold,
  },
  metricDivider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.sm,
  },
  actions: {
    gap: Spacing.md,
  },
  actionBtn: {
    alignSelf: 'stretch',
  },
  progressRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  progressStepWrap: {
    alignItems: 'center',
    flex: 1,
  },
  progressDot: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1.5,
    borderColor: Colors.border,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  progressDotDone: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  progressDotActive: {
    borderColor: Colors.primary,
  },
  progressDotText: {
    fontSize: 11,
    fontWeight: Typography.weights.bold,
    color: Colors.textMuted,
  },
  progressDotTextActive: {
    color: Colors.background,
  },
  progressLabel: {
    fontSize: 8,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  progressLabelActive: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
  },
  chainNote: {
    fontSize: 11,
    color: Colors.primaryLight,
    marginBottom: Spacing.lg,
    marginTop: 2,
  },
  downloadRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  downloadBtn: {
    flex: 1,
  },
  focusBar: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: 4,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  focusBtn: {
    flex: 1,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
    borderRadius: BorderRadius.md,
  },
  focusBtnActive: {
    backgroundColor: Colors.primary,
  },
  focusText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  focusTextActive: {
    color: Colors.textInverse,
    fontWeight: Typography.weights.bold,
  },
  zoomHintRow: {
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  zoomHintText: {
    fontSize: 11,
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
    letterSpacing: 0.2,
  },
  zoomModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
  },
  zoomModalSafe: {
    flex: 1,
  },
  zoomModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  zoomModalTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: '#fff',
  },
  zoomCloseBtn: {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
  },
  zoomCloseText: {
    color: '#fff',
    fontWeight: Typography.weights.bold,
    fontSize: Typography.sizes.xs,
  },
  zoomImageContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.md,
  },
  zoomModalImage: {
    width: '100%',
    height: '100%',
  },
});
