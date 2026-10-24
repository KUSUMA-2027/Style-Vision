import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  Image,
  Modal,
  TextInput} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { api, getApiBaseUrl } from '@/services/api';
import { useStylingSession } from '@/services/session';

type SubCatFilter = 'all' | 'glasses' | 'earrings' | 'necklace' | 'nose_pin' | 'bags';

const SUBCAT_LABEL: Record<string, string> = {
  glasses: '👓 Glasses',
  earrings: '✨ Earrings',
  necklace: '📿 Necklace',
  nose_pin: '🌟 Nose Pin',
  bags: '👜 Bags',
};

const SUBCAT_EMOJI: Record<string, string> = {
  glasses: '👓',
  earrings: '✨',
  necklace: '📿',
  nose_pin: '🌟',
  bags: '👜',
};

interface StyleItem {
  item_id: string;
  name: string;
  category: string;
  subcategory?: string;
  description?: string;
  thumbnail?: string;
  color?: string;
  tags: string[];
}

export default function AccessoriesScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const [items, setItems] = useState<StyleItem[]>([]);
  const [latestPortrait, setLatestPortrait] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [subFilter, setSubFilter] = useState<SubCatFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Manual accessory upload modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [newAccName, setNewAccName] = useState('');
  const [newAccCategory, setNewAccCategory] = useState<'glasses' | 'earrings' | 'necklace' | 'nose_pin' | 'bags'>('glasses');
  const [uploadingAcc, setUploadingAcc] = useState(false);

  const baseUrl = getApiBaseUrl();

  const loadCatalogue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, portraitRes] = await Promise.all([
        api.catalogue.list('accessories'),
        api.upload.getLatest().catch(() => null),
      ]);
      setItems(data.items ?? []);
      if (portraitRes && portraitRes.url) {
        setLatestPortrait(portraitRes);
        session.ensureSession({ image_id: portraitRes.image_id, url: portraitRes.url });
      }
      if (data.items?.length > 0) setSelectedId(data.items[0].item_id);
    } catch (err: any) {
      setError(err.message || 'Could not load accessories catalogue.');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadCatalogue(); }, [loadCatalogue]);

  const filteredItems = items
    .filter((i) => i.subcategory !== 'rings' && i.subcategory !== 'ring' && i.subcategory !== 'bracelet')
    .filter((i) => subFilter === 'all' || i.subcategory === subFilter);

  const handlePickAccessoryPhoto = async (useCamera: boolean = false) => {
    try {
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.7};

      const result = useCamera
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setUploadingAcc(true);
        const defaultName = `My ${newAccCategory.charAt(0).toUpperCase() + newAccCategory.slice(1)}`;
        const nameToUse = newAccName.trim() || defaultName;
        const res = await api.catalogue.uploadAccessory(
          asset.uri,
          nameToUse,
          newAccCategory,
          asset.mimeType || 'image/png'
        );

        setShowAddModal(false);
        setNewAccName('');
        Alert.alert('Accessory Added! ✨', `"${nameToUse}" has been added to your accessories catalogue.`);

        await loadCatalogue();
        setSelectedId(res.item_id);
      }
    } catch (err: any) {
      Alert.alert('Upload Failed', err.message || 'Could not upload accessory photo.');
    } finally {
      setUploadingAcc(false);
    }
  };

  // Effective source image: latest chained result if a styling session is
  // active, otherwise the original uploaded portrait.
  const sourceImage = session.current ??
    (latestPortrait ? { image_id: latestPortrait.image_id, url: latestPortrait.url } : null);
  const appliedStageCount = Object.keys(session.stages).length;
  const isChainedSource = Boolean(session.current && session.stages.accessories?.resultImageId !== session.current.image_id);

  const handleTryOn = async () => {
    if (!selectedId) {
      Alert.alert('Select an Accessory', 'Please choose an accessory from the catalogue.');
      return;
    }
    if (!sourceImage) {
      Alert.alert('Portrait Required', 'Please upload your portrait photo first.');
      return;
    }
    const chosen = items.find((i) => i.item_id === selectedId);
    setIsProcessing(true);
    try {
      const personId = sourceImage.image_id;
      const res = await api.tryon.accessories(personId, selectedId, chosen?.subcategory ?? 'glasses');

      if (res.status === 'failed') {
        Alert.alert('Accessory Fitting Failed', res.error || 'Could not place this accessory on your photo. Please try a different image or accessory.');
        return;
      }

      session.setSelection('accessories', { itemId: selectedId, name: chosen?.name });
      session.applyStageResult({
        stage: 'accessories',
        tryonId: res.tryon_id,
        resultImageId: res.result_image_id ?? null,
        resultUrl: res.result_image_url ?? '',
        sourceUrl: res.original_image_url ?? sourceImage.url,
        title: chosen?.name ?? 'Accessory Try-On',
        style: chosen?.subcategory,
        slot: chosen?.subcategory ?? 'glasses',
        closeupResultUrl: res.closeup_result_image_url ?? null,
        closeupOriginalUrl: res.closeup_original_image_url ?? null,
        appliedAt: Date.now(),
      });

      router.push({
        pathname: '/result',
        params: {
          category: 'accessories',
          title: chosen?.name ?? 'Accessory Try-On',
          style: chosen?.subcategory ? `${chosen.subcategory.toUpperCase()} • ${res.landmark_used || 'Facial Mesh'}` : 'Virtual Accessory',
          itemId: selectedId,
          tryonId: res.tryon_id,
          resultUrl: res.result_image_url,
          originalUrl: res.original_image_url,
          closeupResultUrl: res.closeup_result_image_url || '',
          closeupOriginalUrl: res.closeup_original_image_url || '',
          mode: 'local'}});
    } catch (err: any) {
      Alert.alert('Try-On Error', err.message || 'Could not process accessory placement.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>

        {/* MediaPipe Info Banner */}
        <Card style={styles.engineCard} variant="flat">
          <View style={styles.engineRow}>
            <Text style={styles.engineIcon}>🎯</Text>
            <View style={styles.engineInfo}>
              <Text style={styles.engineTitle}>MediaPipe Landmark Anchoring</Text>
              <Text style={styles.engineDesc}>
                Accessories are placed using detected facial mesh and pose landmarks for accurate spatial fitting.
              </Text>
            </View>
            <Badge label="Landmarks" variant="success" />
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
                    : `${baseUrl}${sourceImage.url}`}}
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
                    ? 'This accessory will be applied on top of your latest styled result.'
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
                <Text style={styles.photoDesc}>Face clearly visible for glasses, earrings, and nose pin.</Text>
              </View>
              <Text style={styles.photoChevron}>→</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Sub-category filter pills */}
        <Text style={styles.sectionHeading}>2. Choose an Accessory</Text>

        {/* Upload Custom Accessory Prompt */}
        <TouchableOpacity
          style={styles.addAccBtn}
          onPress={() => setShowAddModal(true)}
          activeOpacity={0.8}
        >
          <Text style={styles.addAccIcon}>📸</Text>
          <View style={styles.addAccTextWrap}>
            <Text style={styles.addAccTitle}>+ Photograph Your Own Accessory</Text>
            <Text style={styles.addAccDesc}>
              Upload a photo of your sunglasses, earrings, necklace, nose pin, or tote bag
            </Text>
          </View>
          <Text style={styles.addAccChevron}>→</Text>
        </TouchableOpacity>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
          {(['all', 'glasses', 'earrings', 'necklace', 'nose_pin', 'bags'] as SubCatFilter[]).map((key) => {
            const active = subFilter === key;
            return (
              <TouchableOpacity
                key={key}
                style={[styles.pill, active && styles.pillActive]}
                onPress={() => setSubFilter(key)}
              >
                <Text style={[styles.pillText, active && styles.pillTextActive]}>
                  {key === 'all' ? '✦ All' : SUBCAT_LABEL[key]}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Catalogue */}
        {loading && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Loading accessories...</Text>
          </View>
        )}
        {!loading && error && <ErrorMessage message={error} onRetry={loadCatalogue} />}
        {!loading && !error && filteredItems.length === 0 && (
          <View style={styles.emptyWrap}>
            <Text style={styles.emptyIcon}>✨</Text>
            <Text style={styles.emptyText}>No items in this category yet.</Text>
          </View>
        )}

        {!loading && !error && filteredItems.length > 0 && (
          <View style={styles.grid}>
            {filteredItems.map((item) => {
              const isSelected = item.item_id === selectedId;
              const emoji = SUBCAT_EMOJI[item.subcategory ?? ''] ?? '💎';
              const photoUri = item.thumbnail
                ? item.thumbnail.startsWith('http')
                  ? item.thumbnail
                  : `${baseUrl}${item.thumbnail}`
                : null;
              return (
                <TouchableOpacity
                  key={item.item_id}
                  style={[styles.itemCard, isSelected && styles.itemCardSelected]}
                  onPress={() => setSelectedId(item.item_id)}
                  activeOpacity={0.7}
                >
                  {photoUri ? (
                    <Image source={{ uri: photoUri }} style={styles.accessoryPhoto} resizeMode="contain" />
                  ) : (
                    <View style={styles.itemEmojiWrap}>
                      <View style={[styles.colorDot, { backgroundColor: item.color ?? Colors.primary }]} />
                      <Text style={styles.itemEmoji}>{emoji}</Text>
                    </View>
                  )}
                  <Text style={styles.itemName} numberOfLines={2}>{item.name}</Text>
                  {item.subcategory && (
                    <Text style={styles.itemSub}>{SUBCAT_LABEL[item.subcategory] ?? item.subcategory}</Text>
                  )}
                  {isSelected && (
                    <View style={styles.tick}><Text style={styles.tickText}>✓</Text></View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Landmark info for selected */}
        {selectedId && (() => {
          const item = items.find((i) => i.item_id === selectedId);
          const anchorMap: Record<string, string> = {
            glasses: 'Eye Bridge (Facial Mesh #168)',
            earrings: 'Earlobes (Mesh #234, #454)',
            necklace: 'Collarbones (Pose #11, #12)',
            nose_pin: 'Nostril Curve (Mesh #278)',
            bags: 'Shoulder Pose (#11)',
          };
          return item ? (
            <Card style={styles.descCard} variant="outlined">
              <Text style={styles.descTitle}>{item.name}</Text>
              {item.description && <Text style={styles.descText}>{item.description}</Text>}
              {item.subcategory && anchorMap[item.subcategory] && (
                <View style={styles.anchorRow}>
                  <Text style={styles.anchorLabel}>📍 Landmark: </Text>
                  <Text style={styles.anchorValue}>{anchorMap[item.subcategory]}</Text>
                </View>
              )}
            </Card>
          ) : null;
        })()}

        <Button
          title={isProcessing ? 'Fitting...' : 'Fit Accessory ✨'}
          variant="primary"
          size="lg"
          loading={isProcessing}
          disabled={!selectedId || loading}
          onPress={handleTryOn}
          style={styles.tryOnBtn}
        />
      </ScrollView>

      {/* Add Accessory Modal */}
      <Modal visible={showAddModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <Card style={styles.modalCard} variant="elevated">
            <Text style={styles.modalTitle}>Upload My Own Accessory 💎</Text>
            <Text style={styles.modalSubtitle}>
              Photograph sunglasses, earrings, a necklace, a nose pin, or a handbag/tote bag to try on.
            </Text>

            <Text style={styles.inputLabel}>Accessory Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. My Gold Jhumka Earrings"
              placeholderTextColor={Colors.textMuted}
              value={newAccName}
              onChangeText={setNewAccName}
            />

            <Text style={styles.inputLabel}>Accessory Type</Text>
            <View style={styles.modalCatRow}>
              {(
                [
                  { key: 'glasses', label: '👓 Glasses' },
                  { key: 'earrings', label: '✨ Earrings' },
                  { key: 'necklace', label: '📿 Necklace' },
                  { key: 'nose_pin', label: '🌟 Nose Pin' },
                  { key: 'bags', label: '👜 Tote Bag' },
                ] as const
              ).map((cat) => {
                const active = newAccCategory === cat.key;
                return (
                  <TouchableOpacity
                    key={cat.key}
                    style={[styles.modalCatBtn, active && styles.modalCatBtnActive]}
                    onPress={() => setNewAccCategory(cat.key)}
                  >
                    <Text style={[styles.modalCatText, active && styles.modalCatTextActive]}>
                      {cat.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {uploadingAcc ? (
              <View style={styles.modalLoading}>
                <ActivityIndicator size="large" color={Colors.primary} />
                <Text style={styles.modalLoadingText}>Processing accessory & removing background...</Text>
              </View>
            ) : (
              <View style={styles.modalActions}>
                <Button
                  title="📷 Take Photo"
                  variant="primary"
                  size="md"
                  onPress={() => handlePickAccessoryPhoto(true)}
                  style={styles.modalActionBtn}
                />
                <Button
                  title="🖼️ Gallery"
                  variant="outline"
                  size="md"
                  onPress={() => handlePickAccessoryPhoto(false)}
                  style={styles.modalActionBtn}
                />
                <Button
                  title="Cancel"
                  variant="ghost"
                  size="md"
                  onPress={() => setShowAddModal(false)}
                  style={styles.modalActionBtn}
                />
              </View>
            )}
          </Card>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: Colors.background },
  container: { flex: 1 },
  content: { padding: Spacing.lg, paddingBottom: Spacing.xxxl * 2 },
  engineCard: {
    backgroundColor: Colors.surfaceCard,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border},
  engineRow: { flexDirection: 'row', alignItems: 'flex-start' },
  engineIcon: { fontSize: 24, marginRight: Spacing.md },
  engineInfo: { flex: 1 },
  engineTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 2},
  engineDesc: { fontSize: Typography.sizes.xs, color: Colors.textMuted, lineHeight: 16 },
  sectionHeading: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: Spacing.sm,
    marginTop: Spacing.sm},
  photoCard: {
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
    width: '100%'},
  portraitThumb: {
    width: 52,
    height: 52,
    borderRadius: BorderRadius.md,
    marginRight: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.primary},
  validatedBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginBottom: 2},
  photoIcon: { fontSize: 28, marginRight: Spacing.md },
  photoTextWrap: { flex: 1 },
  photoTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight},
  photoDesc: { fontSize: Typography.sizes.xs, color: Colors.textMuted, marginTop: 2 },
  photoChevron: { fontSize: 20, color: Colors.primaryLight },
  filterRow: { paddingBottom: Spacing.sm, gap: Spacing.sm, marginBottom: Spacing.md },
  pill: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border},
  pillActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  pillText: { fontSize: Typography.sizes.xs, color: Colors.textMuted, fontWeight: Typography.weights.medium },
  pillTextActive: { color: Colors.textInverse, fontWeight: Typography.weights.bold },
  loadingWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  loadingText: { color: Colors.textMuted, fontSize: Typography.sizes.xs, marginTop: Spacing.sm },
  emptyWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  emptyIcon: { fontSize: 40, marginBottom: Spacing.sm },
  emptyText: { color: Colors.textMuted, fontSize: Typography.sizes.sm },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginBottom: Spacing.lg },
  itemCard: {
    width: '47%',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.md,
    borderWidth: 2,
    borderColor: Colors.border,
    padding: Spacing.md,
    alignItems: 'center',
    position: 'relative'},
  itemCardSelected: { borderColor: Colors.primary, backgroundColor: Colors.primaryGlow },
  colorDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    marginBottom: Spacing.xs,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.2)'},
  accessoryPhoto: {
    width: '100%',
    height: 72,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.xs,
    backgroundColor: Colors.surface,
  },
  itemEmojiWrap: {
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  itemEmoji: { fontSize: 26, marginBottom: Spacing.xs },
  itemName: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    textAlign: 'center'},
  itemSub: { fontSize: 10, color: Colors.textMuted, marginTop: 2 },
  tick: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center'},
  tickText: { color: Colors.textInverse, fontSize: 12, fontWeight: '800' },
  descCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.md,
    marginBottom: Spacing.lg},
  descTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 4},
  descText: { fontSize: Typography.sizes.xs, color: Colors.textSecondary, lineHeight: 18, marginBottom: Spacing.xs },
  anchorRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  anchorLabel: { fontSize: Typography.sizes.xs, color: Colors.textMuted },
  anchorValue: { fontSize: Typography.sizes.xs, color: Colors.primaryLight, fontWeight: Typography.weights.bold },
  tryOnBtn: { marginTop: Spacing.sm },
  addAccBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    borderWidth: 1.5,
    borderColor: Colors.primary,
    borderStyle: 'dashed',
    padding: Spacing.md,
    marginBottom: Spacing.md},
  addAccIcon: {
    fontSize: 24,
    marginRight: Spacing.md},
  addAccTextWrap: {
    flex: 1},
  addAccTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight},
  addAccDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 2},
  addAccChevron: {
    fontSize: Typography.sizes.md,
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold},
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.lg},
  modalCard: {
    width: '100%',
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.xl,
    borderRadius: BorderRadius.xl,
    borderWidth: 1,
    borderColor: Colors.border},
  modalTitle: {
    fontSize: Typography.sizes.lg,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 4},
  modalSubtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginBottom: Spacing.lg},
  inputLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    marginBottom: 4,
    fontWeight: Typography.weights.medium},
  input: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    color: Colors.textPrimary,
    fontSize: Typography.sizes.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.md},
  modalCatRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: Spacing.lg},
  modalCatBtn: {
    paddingHorizontal: Spacing.sm + 2,
    paddingVertical: 6,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border},
  modalCatBtnActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary},
  modalCatText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium},
  modalCatTextActive: {
    color: '#fff',
    fontWeight: Typography.weights.bold},
  modalLoading: {
    alignItems: 'center',
    paddingVertical: Spacing.lg},
  modalLoadingText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: Spacing.sm},
  modalActions: {
    flexDirection: 'row',
    gap: Spacing.sm},
  modalActionBtn: {
    flex: 1}});
