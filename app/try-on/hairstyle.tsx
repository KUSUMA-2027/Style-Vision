import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator,
  Modal,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
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
  thumbnail?: string;
  color?: string;
  tags: string[];
  is_custom?: boolean;
}

interface HairColor {
  id: string;
  name: string;
  hex: string;
}

type HairSubCat = 'all' | 'short' | 'medium' | 'long' | 'updo';

const HAIR_EMOJIS: Record<string, string> = {
  short: '💇‍♂️',
  medium: '👩‍🦱',
  long: '👱‍♀️',
  updo: '💇‍♀️',
};

export default function HairstyleScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const baseUrl = getApiBaseUrl();
  const [items, setItems] = useState<StyleItem[]>([]);
  const [latestPortrait, setLatestPortrait] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedColor, setSelectedColor] = useState<string>('c-1');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [subFilter, setSubFilter] = useState<HairSubCat>('all');

  // Custom upload modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [uploadingHair, setUploadingHair] = useState(false);
  const [newHairName, setNewHairName] = useState('');
  const [newHairCategory, setNewHairCategory] = useState<'short' | 'medium' | 'long' | 'updo'>('medium');

  const colors: HairColor[] = [
    { id: 'c-1', name: 'Jet Black', hex: '#1C1C1E' },
    { id: 'c-2', name: 'Mocha Brown', hex: '#4E342E' },
    { id: 'c-3', name: 'Honey Blonde', hex: '#D4AF37' },
    { id: 'c-4', name: 'Burgundy Wine', hex: '#581845' },
    { id: 'c-5', name: 'Platinum Ice', hex: '#B0BEC5' },
  ];

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [catData, portraitData] = await Promise.all([
        api.catalogue.list('hairstyle'),
        api.upload.getLatest().catch(() => null),
      ]);
      setItems(catData.items ?? []);
      if (portraitData) {
        setLatestPortrait(portraitData);
        session.ensureSession({ image_id: portraitData.image_id, url: portraitData.url });
      }
      if (catData.items?.length > 0 && !selectedId) {
        setSelectedId(catData.items[0].item_id);
      }
    } catch (err: any) {
      setError(err.message || 'Could not load hairstyle catalogue.');
    } finally {
      setLoading(false);
    }
  }, [selectedId, session]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handlePickImage = async (useCamera: boolean) => {
    try {
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ['images'],
        allowsEditing: true,
        quality: 0.8,
      };

      const result = useCamera
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setUploadingHair(true);
        const defaultName = `My ${newHairCategory.charAt(0).toUpperCase() + newHairCategory.slice(1)} Hair`;
        const nameToUse = newHairName.trim() || defaultName;
        const res = await api.catalogue.uploadHairstyle(
          asset.uri,
          nameToUse,
          newHairCategory,
          asset.mimeType || 'image/png'
        );

        setShowAddModal(false);
        setNewHairName('');
        Alert.alert('Hairstyle Added! ✨', `"${nameToUse}" has been added to your hairstyle catalogue.`);

        await loadData();
        setSelectedId(res.item_id);
      }
    } catch (err: any) {
      Alert.alert('Upload Failed', err.message || 'Could not upload hairstyle photo.');
    } finally {
      setUploadingHair(false);
    }
  };

  const handleDeleteHairstyle = (item: StyleItem) => {
    Alert.alert('Remove Hairstyle', `Delete "${item.name}" from your hairstyle collection?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.catalogue.deleteItem(item.item_id);
            if (selectedId === item.item_id) {
              setSelectedId(null);
            }
            await loadData();
            Alert.alert('Removed', `"${item.name}" has been deleted.`);
          } catch (err: any) {
            Alert.alert('Delete Failed', err.message || 'Could not delete hairstyle.');
          }
        },
      },
    ]);
  };

  // Filtered catalogue items
  const filteredItems = items.filter((item) => {
    if (subFilter === 'all') return true;
    return (item.subcategory?.toLowerCase() || '') === subFilter;
  });

  // Effective source image: latest chained result if a styling session is active
  const sourceImage = session.current ??
    (latestPortrait ? { image_id: latestPortrait.image_id, url: latestPortrait.url } : null);
  const appliedStageCount = Object.keys(session.stages).length;
  const isChainedSource = Boolean(session.current && session.stages.hairstyle?.resultImageId !== session.current.image_id);

  const handleApply = async () => {
    if (!selectedId) {
      Alert.alert('Select Hairstyle', 'Please choose a hairstyle from the catalogue.');
      return;
    }
    if (!sourceImage) {
      Alert.alert('Portrait Required', 'Please upload your portrait photo first.');
      return;
    }
    const chosenStyle = items.find((h) => h.item_id === selectedId);
    const chosenColor = colors.find((c) => c.id === selectedColor);
    setIsProcessing(true);
    try {
      const personId = sourceImage.image_id;
      const res = await api.tryon.hairstyle(personId, selectedId, chosenColor?.hex);

      if (res.status === 'failed') {
        Alert.alert('Hairstyle Fitting Failed', res.error || 'No face/head could be detected in the current image. Please use a clear, front-facing photo.');
        return;
      }

      session.setSelection('hairstyle', { itemId: selectedId, name: chosenStyle?.name, color: chosenColor?.name });
      session.applyStageResult({
        stage: 'hairstyle',
        tryonId: res.tryon_id,
        resultImageId: res.result_image_id ?? null,
        resultUrl: res.result_image_url ?? '',
        sourceUrl: res.original_image_url ?? sourceImage.url,
        title: chosenStyle?.name ?? 'Hairstyle Look',
        style: chosenColor?.name ?? 'Natural Color',
        closeupResultUrl: res.closeup_result_image_url ?? null,
        closeupOriginalUrl: res.closeup_original_image_url ?? null,
        appliedAt: Date.now(),
      });

      router.push({
        pathname: '/result',
        params: {
          category: 'hairstyle',
          title: chosenStyle?.name ?? 'Hairstyle Look',
          style: `${chosenColor?.name ?? 'Natural Color'} • Head Alignment`,
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
      Alert.alert('Try-On Error', err.message || 'Could not process hairstyle fitting.');
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
            <Text style={styles.engineIcon}>👑</Text>
            <View style={styles.engineInfo}>
              <Text style={styles.engineTitle}>Haute Coiffure Salon</Text>
              <Text style={styles.engineDesc}>
                Precision cranial contouring & couture pigment matching
              </Text>
            </View>
            <Badge label="Haute Styling" variant="primary" />
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
                    label={isChainedSource ? `${appliedStageCount} Stage${appliedStageCount > 1 ? 's' : ''} Applied` : 'Head Alignment'}
                    variant={isChainedSource ? 'primary' : 'success'}
                  />
                </View>
                <Text style={styles.photoDesc}>
                  {isChainedSource
                    ? 'Hairstyle will preserve your outfit, accessories, and makeup.'
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
                <Text style={styles.photoDesc}>Hairline and forehead visible without hats or obstructions.</Text>
              </View>
              <Text style={styles.photoChevron}>→</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Hairstyle Selection Grid */}
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionHeading}>2. Select Hairstyle</Text>
          <TouchableOpacity
            style={styles.addHairBtn}
            onPress={() => setShowAddModal(true)}
            activeOpacity={0.8}
          >
            <Text style={styles.addHairBtnText}>+ Upload Style</Text>
          </TouchableOpacity>
        </View>

        {/* Category Filter Pills */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
          {(['all', 'short', 'medium', 'long', 'updo'] as const).map((key) => {
            const active = subFilter === key;
            return (
              <TouchableOpacity
                key={key}
                style={[styles.pill, active && styles.pillActive]}
                onPress={() => setSubFilter(key)}
              >
                <Text style={[styles.pillText, active && styles.pillTextActive]}>
                  {key === 'all' ? '✦ All Styles' : `${HAIR_EMOJIS[key]} ${key.charAt(0).toUpperCase() + key.slice(1)}`}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {loading && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Loading hairstyles...</Text>
          </View>
        )}

        {!loading && error && (
          <ErrorMessage message={error} onRetry={loadData} />
        )}

        {!loading && !error && filteredItems.length === 0 && (
          <View style={styles.emptyWrap}>
            <Text style={styles.emptyIcon}>💇‍♀️</Text>
            <Text style={styles.emptyText}>No hairstyles in this category yet.</Text>
          </View>
        )}

        {!loading && !error && filteredItems.length > 0 && (
          <View style={styles.stylesGrid}>
            {filteredItems.map((hair) => {
              const isSelected = selectedId === hair.item_id;
              const emoji = HAIR_EMOJIS[hair.subcategory ?? 'medium'] ?? '💇‍♀️';
              const photoUri = hair.thumbnail
                ? hair.thumbnail.startsWith('http')
                  ? hair.thumbnail
                  : `${baseUrl}${hair.thumbnail}`
                : null;
              const isCustom =
                hair.item_id.includes('custom') ||
                hair.tags?.includes('custom') ||
                Boolean((hair as any).is_custom) ||
                Boolean(hair.thumbnail?.includes('/uploads/hairstyles/'));

              return (
                <TouchableOpacity
                  key={hair.item_id}
                  activeOpacity={0.8}
                  onPress={() => setSelectedId(hair.item_id)}
                  style={[
                    styles.hairCard,
                    isSelected && styles.hairCardSelected,
                  ]}
                >
                  {isCustom && (
                    <TouchableOpacity
                      style={styles.deleteHairBtn}
                      onPress={(e) => {
                        e.stopPropagation?.();
                        handleDeleteHairstyle(hair);
                      }}
                      hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                    >
                      <Text style={styles.deleteHairText}>✕</Text>
                    </TouchableOpacity>
                  )}

                  {photoUri ? (
                    <Image source={{ uri: photoUri }} style={styles.hairPhoto} resizeMode="contain" />
                  ) : (
                    <View style={styles.hairEmojiWrap}>
                      <Text style={styles.hairEmoji}>{emoji}</Text>
                    </View>
                  )}
                  <Text style={styles.hairName} numberOfLines={2}>
                    {hair.name}
                  </Text>
                  {hair.subcategory && (
                    <Badge
                      label={isCustom ? `CUSTOM • ${hair.subcategory.toUpperCase()}` : hair.subcategory.toUpperCase()}
                      variant={isCustom ? 'primary' : isSelected ? 'primary' : 'muted'}
                    />
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Hair Color Selection */}
        <Text style={styles.sectionHeading}>3. Select Color Tint</Text>
        <View style={styles.colorRow}>
          {colors.map((color) => {
            const isSelected = selectedColor === color.id;
            return (
              <TouchableOpacity
                key={color.id}
                onPress={() => setSelectedColor(color.id)}
                style={[
                  styles.colorOption,
                  isSelected && styles.colorOptionSelected,
                ]}
              >
                <View style={[styles.colorDot, { backgroundColor: color.hex }]} />
                <Text style={[styles.colorLabel, isSelected && styles.colorLabelSelected]}>
                  {color.name}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Action Button */}
        <Button
          title={isProcessing ? 'Aligning Hairstyle Mesh...' : 'Explore Hairstyle Look 💇'}
          variant="primary"
          size="lg"
          loading={isProcessing}
          disabled={!selectedId || loading}
          onPress={handleApply}
          style={styles.actionBtn}
        />
      </ScrollView>

      {/* Upload Hairstyle Modal */}
      <Modal
        visible={showAddModal}
        animationType="slide"
        transparent
        onRequestClose={() => !uploadingHair && setShowAddModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeaderRow}>
              <Text style={styles.modalTitle}>Upload Custom Hairstyle</Text>
              <TouchableOpacity
                onPress={() => setShowAddModal(false)}
                disabled={uploadingHair}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Upload a hairstyle photograph, wig, or portrait. StyleVision will automatically isolate the hair texture and fit it to your head geometry.
            </Text>

            <Text style={styles.inputLabel}>Hairstyle Name (optional)</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Honey Caramel Waves"
              placeholderTextColor="#666"
              value={newHairName}
              onChangeText={setNewHairName}
              editable={!uploadingHair}
            />

            <Text style={styles.inputLabel}>Hairstyle Length / Style</Text>
            <View style={styles.modalCatRow}>
              {(['short', 'medium', 'long', 'updo'] as const).map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[
                    styles.modalCatBtn,
                    newHairCategory === cat && styles.modalCatBtnActive,
                  ]}
                  onPress={() => setNewHairCategory(cat)}
                  disabled={uploadingHair}
                >
                  <Text
                    style={[
                      styles.modalCatText,
                      newHairCategory === cat && styles.modalCatTextActive,
                    ]}
                  >
                    {HAIR_EMOJIS[cat]} {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {uploadingHair ? (
              <View style={styles.modalLoading}>
                <ActivityIndicator size="large" color={Colors.primary} />
                <Text style={styles.modalLoadingText}>Isolating hair & removing background...</Text>
              </View>
            ) : (
              <View style={styles.modalActions}>
                <Button
                  title="📸 Take Photo"
                  variant="outline"
                  onPress={() => handlePickImage(true)}
                  style={styles.modalActionBtn}
                />
                <Button
                  title="🖼️ From Gallery"
                  variant="primary"
                  onPress={() => handlePickImage(false)}
                  style={styles.modalActionBtn}
                />
              </View>
            )}
          </View>
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
  engineCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  engineRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  engineIcon: {
    fontSize: 24,
    marginRight: Spacing.md,
  },
  engineInfo: {
    flex: 1,
  },
  engineTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
  },
  engineDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2,
  },
  photoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primaryGlow,
    borderStyle: 'dashed',
    padding: Spacing.md,
    marginBottom: Spacing.xl,
  },
  portraitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  portraitThumb: {
    width: 52,
    height: 52,
    borderRadius: BorderRadius.md,
    borderWidth: 1.5,
    borderColor: Colors.primary,
  },
  validatedBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: 2,
  },
  photoIcon: { fontSize: 28, marginRight: Spacing.md },
  photoTextWrap: { flex: 1 },
  photoTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
  },
  photoDesc: { fontSize: Typography.sizes.xs, color: Colors.textMuted, marginTop: 2 },
  photoChevron: { fontSize: 20, color: Colors.primaryLight },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  sectionHeading: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  addHairBtn: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 5,
    borderRadius: BorderRadius.full,
    backgroundColor: 'rgba(212, 175, 55, 0.15)',
    borderWidth: 1,
    borderColor: Colors.primary,
  },
  addHairBtnText: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight,
  },
  filterRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
    marginBottom: Spacing.lg,
  },
  pill: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs + 2,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  pillActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  pillText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  pillTextActive: {
    color: '#0D0D12',
    fontWeight: Typography.weights.bold,
  },
  loadingWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  loadingText: { color: Colors.textMuted, fontSize: Typography.sizes.xs, marginTop: Spacing.sm },
  emptyWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  emptyIcon: { fontSize: 40, marginBottom: Spacing.sm },
  emptyText: { color: Colors.textMuted, fontSize: Typography.sizes.sm },
  stylesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: Spacing.xxl,
  },
  hairCard: {
    width: '48%',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.border,
    alignItems: 'center',
    position: 'relative',
  },
  hairCardSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primaryGlow,
  },
  deleteHairBtn: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: '#FF3B30',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  deleteHairText: {
    color: '#FFF',
    fontSize: 11,
    fontWeight: 'bold',
    lineHeight: 13,
  },
  hairPhoto: {
    width: '100%',
    height: 90,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
    backgroundColor: Colors.surface,
  },
  hairEmojiWrap: {
    width: 60,
    height: 60,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  hairEmoji: {
    fontSize: 32,
  },
  hairName: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 4,
    textAlign: 'center',
  },
  colorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginBottom: Spacing.xxl,
  },
  colorOption: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  colorOptionSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primaryGlow,
  },
  colorDot: {
    width: 14,
    height: 14,
    borderRadius: 7,
    marginRight: Spacing.sm,
    borderWidth: 1,
    borderColor: '#FFFFFF44',
  },
  colorLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
  },
  colorLabelSelected: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
  },
  actionBtn: {
    marginTop: Spacing.sm,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.lg,
  },
  modalCard: {
    width: '100%',
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.xl,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  modalTitle: {
    fontSize: Typography.sizes.lg,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
  },
  modalCloseText: {
    fontSize: 18,
    color: Colors.textMuted,
    fontWeight: 'bold',
  },
  modalSubtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginBottom: Spacing.lg,
    lineHeight: 18,
  },
  inputLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    marginBottom: 4,
    fontWeight: Typography.weights.medium,
  },
  input: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    color: Colors.textPrimary,
    fontSize: Typography.sizes.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.md,
  },
  modalCatRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: Spacing.lg,
  },
  modalCatBtn: {
    paddingHorizontal: Spacing.sm + 4,
    paddingVertical: 7,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalCatBtnActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  modalCatText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  modalCatTextActive: {
    color: '#0D0D12',
    fontWeight: Typography.weights.bold,
  },
  modalLoading: {
    alignItems: 'center',
    paddingVertical: Spacing.lg,
  },
  modalLoadingText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: Spacing.sm,
  },
  modalActions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  modalActionBtn: {
    flex: 1,
  },
});
