/**
 * StyleVision — Complete Look Screen
 * Final stage of the styling workflow: displays the combined result of all
 * applied stages (outfit → accessories → makeup → hairstyle), lets the user
 * revisit any stage, save the look, download it, or start a new session.
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Header } from '@/components/ui/Header';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { getApiBaseUrl, api } from '@/services/api';
import { downloadImageToLibrary, shareImage } from '@/services/saveMedia';
import {
  useStylingSession,
  STAGE_ORDER,
  STAGE_LABEL,
  STAGE_ROUTE,
  type Stage,
  type SessionItem,
} from '@/services/session';

const STAGE_ICON: Record<Stage, string> = {
  outfit: '👗',
  accessories: '💎',
  makeup: '💄',
  hairstyle: '💇',
};

export default function CompleteLookScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const baseUrl = getApiBaseUrl();

  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const appliedStages = STAGE_ORDER.filter((s) => session.stages[s]);
  const hasLook = Boolean(session.current && appliedStages.length > 0);
  const finalImageUrl = session.current?.url
    ? session.current.url.startsWith('http')
      ? session.current.url
      : `${baseUrl}${session.current.url}`
    : null;

  const resolvedTryonId =
    [...appliedStages].reverse().map((s) => session.stages[s]!.tryonId).find(Boolean) || '';

  const handleRemoveItem = async (item: SessionItem) => {
    Alert.alert('Remove Item', `Remove "${item.title}" from your look?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          setRemovingId(item.imageId);
          try {
            const done = await session.removeItem(item);
            if (done) {
              Alert.alert('Removed ✓', `"${item.title}" has been removed from your look.`);
            } else {
              Alert.alert('Remove Failed', 'Could not rebuild the look without this item.');
            }
          } catch (err: any) {
            Alert.alert('Remove Failed', err.message || 'Could not remove this item.');
          } finally {
            setRemovingId(null);
          }
        },
      },
    ]);
  };

  const handleSave = async () => {
    if (!resolvedTryonId) return;
    setSaving(true);
    try {
      const stageMeta = appliedStages.map((s) => ({
        stage: s,
        tryon_id: session.stages[s]!.tryonId,
        result_image_id: session.stages[s]!.resultImageId,
        result_image_url: session.stages[s]!.resultUrl,
        title: session.stages[s]!.title,
      }));
      await api.history.save(resolvedTryonId, 'My Complete Look', {
        base_image_id: session.base?.image_id,
        final_image_id: session.current?.image_id,
        stages: stageMeta,
        category: 'complete',
      });
      Alert.alert('Look Saved! 💎', 'Your complete look is now in your Atelier Lookbook.');
    } catch (err: any) {
      Alert.alert('Save Failed', err.message || 'Could not save this look right now.');
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    if (!finalImageUrl) return;
    setDownloading(true);
    try {
      const result = await downloadImageToLibrary(finalImageUrl, 'stylevision-complete-look.png');
      if (result.ok) {
        Alert.alert('Downloaded! 📥', result.message);
      } else {
        Alert.alert('Download Notice', result.message);
      }
    } catch (err: any) {
      Alert.alert('Download Failed', err.message || 'Could not download the image right now.');
    } finally {
      setDownloading(false);
    }
  };

  const handleShare = async () => {
    if (!finalImageUrl) return;
    try {
      await shareImage(finalImageUrl, 'stylevision-complete-look.png');
    } catch (err: any) {
      Alert.alert('Share Failed', err.message || 'Could not share the image right now.');
    }
  };

  const handleStartNew = () => {
    Alert.alert(
      'Start a New Look?',
      'This clears the current styling session. Your saved looks remain in your Lookbook.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Start New',
          style: 'destructive',
          onPress: () => {
            session.resetSession();
            router.push('/upload');
          },
        },
      ]
    );
  };

  if (!session.base && !hasLook) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <Header title="Complete Look" showBack />
        <EmptyState
          icon="✨"
          title="No Styling Session Yet"
          description="Upload a portrait and style your outfit, accessories, makeup, and hairstyle — then return here for the combined reveal."
          actionTitle="Start Styling"
          onAction={() => router.push('/upload')}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Badge label="Final Reveal" variant="primary" style={styles.badge} />
          <Text style={styles.title}>Your Complete Look</Text>
          <Text style={styles.subtitle}>
            {appliedStages.length === 0
              ? 'No stages applied yet — start with an outfit.'
              : `${appliedStages.length} of 4 stages applied`}
          </Text>
        </View>

        {/* Combined result preview */}
        <Card style={styles.previewCard} variant="elevated">
          {finalImageUrl ? (
            <Image source={{ uri: finalImageUrl }} style={styles.previewImage} resizeMode="cover" />
          ) : (
            <View style={styles.previewPlaceholder}>
              <Text style={styles.previewPlaceholderIcon}>🪞</Text>
              <Text style={styles.previewPlaceholderText}>Apply stages to reveal your look</Text>
            </View>
          )}
        </Card>

        {/* Stage checklist — free navigation: revisit any stage in ANY order */}
        <Text style={styles.sectionHeading}>Styling Stages</Text>
        <Card style={styles.stagesCard} variant="outlined">
          {STAGE_ORDER.map((stage) => {
            const result = session.stages[stage];
            const done = Boolean(result);
            return (
              <TouchableOpacity
                key={stage}
                style={styles.stageRow}
                onPress={() => router.push(STAGE_ROUTE[stage] as any)}
                activeOpacity={0.7}
              >
                <Text style={styles.stageIcon}>{STAGE_ICON[stage]}</Text>
                <View style={styles.stageInfo}>
                  <View style={styles.stageTitleRow}>
                    <Text style={styles.stageName}>{STAGE_LABEL[stage]}</Text>
                    {done && (() => {
                      const isCloud = stage === 'outfit';
                      return (
                        <View
                          style={[
                            styles.sourcePillSmall,
                            isCloud ? styles.pillGpuSmall : styles.pillLocalSmall,
                          ]}
                        >
                          <Text
                            style={[
                              styles.sourcePillSmallText,
                              isCloud ? styles.pillTextGpuSmall : styles.pillTextLocalSmall,
                            ]}
                          >
                            {isCloud ? '🚀 Cloud AI' : '⚡ Local AI'}
                          </Text>
                        </View>
                      );
                    })()}
                  </View>
                  <Text style={styles.stageDetail} numberOfLines={1}>
                    {done ? result!.title : 'Tap to style — any order you like'}
                  </Text>
                </View>
                <Badge
                  label={done ? '✓ Applied' : 'Add'}
                  variant={done ? 'success' : 'muted'}
                />
              </TouchableOpacity>
            );
          })}
        </Card>
        <Text style={styles.revisitNote}>
          Style in any order — jump straight to jewelry, hair, or makeup. Tap an applied stage to
          change it.
        </Text>

        {/* Applied items — individual remove */}
        {session.items.length > 0 && (
          <>
            <Text style={styles.sectionHeading}>Applied Items ({session.items.length})</Text>
            <Card style={styles.stagesCard} variant="outlined">
              {session.items.map((item) => {
                const isCloud = item.stage === 'outfit';
                return (
                  <View key={item.imageId} style={styles.stageRow}>
                    <Text style={styles.stageIcon}>{STAGE_ICON[item.stage as Stage] ?? '✨'}</Text>
                    <View style={styles.stageInfo}>
                      <View style={styles.stageTitleRow}>
                        <Text style={styles.stageName} numberOfLines={1}>
                          {item.title}
                        </Text>
                        <View
                          style={[
                            styles.sourcePillSmall,
                            isCloud ? styles.pillGpuSmall : styles.pillLocalSmall,
                          ]}
                        >
                          <Text
                            style={[
                              styles.sourcePillSmallText,
                              isCloud ? styles.pillTextGpuSmall : styles.pillTextLocalSmall,
                            ]}
                          >
                            {isCloud ? '🚀 Cloud AI' : '⚡ Local AI'}
                          </Text>
                        </View>
                      </View>
                      <Text style={styles.stageDetail}>
                        {STAGE_LABEL[item.stage as Stage] ?? item.stage}
                        {item.slot ? ` • ${item.slot}` : ''}
                      </Text>
                    </View>
                  {removingId === item.imageId ? (
                    <ActivityIndicator size="small" color={Colors.primary} />
                  ) : (
                    <TouchableOpacity
                      onPress={() => handleRemoveItem(item)}
                      style={styles.removeItemBtn}
                      accessibilityLabel={`Remove ${item.title}`}
                    >
                      <Text style={styles.removeItemText}>🗑 Remove</Text>
                    </TouchableOpacity>
                  )}
                </View>
                );
              })}
            </Card>
          </>
        )}

        {/* Actions */}
        <View style={styles.actions}>
          <Button
            title={saving ? 'Saving...' : 'Save to Lookbook 💜'}
            variant="primary"
            size="lg"
            onPress={handleSave}
            disabled={saving || !hasLook}
            loading={saving}
            style={styles.actionBtn}
          />
          <View style={styles.rowBtns}>
            <Button
              title={downloading ? 'Downloading...' : 'Download 📥'}
              variant="outline"
              size="md"
              onPress={handleDownload}
              disabled={downloading || !hasLook}
              loading={downloading}
              style={styles.halfBtn}
            />
            <Button
              title="Share"
              variant="outline"
              size="md"
              onPress={handleShare}
              disabled={!hasLook}
              style={styles.halfBtn}
            />
          </View>
          <Button
            title="Try Once Again 🔄"
            variant="outline"
            size="md"
            onPress={() => {
              const lastStage = [...appliedStages].reverse()[0] || 'hairstyle';
              router.push(STAGE_ROUTE[lastStage] as any);
            }}
            style={styles.actionBtn}
          />
          <Button
            title="Start a New Look"
            variant="ghost"
            size="md"
            onPress={handleStartNew}
            style={styles.actionBtn}
          />
        </View>
      </ScrollView>
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
  previewCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.md,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  previewImage: {
    width: '100%',
    height: 420,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surface,
  },
  previewPlaceholder: {
    width: '100%',
    height: 300,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  previewPlaceholderIcon: {
    fontSize: 48,
    marginBottom: Spacing.sm,
  },
  previewPlaceholderText: {
    fontSize: Typography.sizes.sm,
    color: Colors.textMuted,
  },
  sectionHeading: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: Spacing.sm,
  },
  stagesCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  stageRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.xs,
  },
  stageIcon: {
    fontSize: 22,
    marginRight: Spacing.md,
  },
  stageInfo: {
    flex: 1,
    marginRight: Spacing.sm,
  },
  stageTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sourcePillSmall: {
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
  },
  pillGpuSmall: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.4)',
  },
  pillLocalSmall: {
    backgroundColor: 'rgba(59, 130, 246, 0.15)',
    borderColor: 'rgba(59, 130, 246, 0.4)',
  },
  sourcePillSmallText: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  pillTextGpuSmall: {
    color: '#10B981',
  },
  pillTextLocalSmall: {
    color: '#60A5FA',
  },
  stageName: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
  },
  stageDetail: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2,
  },
  revisitNote: {
    fontSize: 11,
    color: Colors.textMuted,
    marginBottom: Spacing.xl,
    lineHeight: 16,
  },
  removeItemBtn: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  removeItemText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    fontWeight: Typography.weights.bold,
  },
  actions: {
    gap: Spacing.md,
  },
  actionBtn: {
    alignSelf: 'stretch',
  },
  rowBtns: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  halfBtn: {
    flex: 1,
  },
});
