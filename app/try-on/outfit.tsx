import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  TextInput,
  Modal,
  Image} from 'react-native';
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

interface GarmentItem {
  id: string;
  name: string;
  category: string;
  color?: string;
  imageUrl?: string;
  isWardrobe?: boolean;
}

interface PortraitInfo {
  image_id: string;
  url: string;
  width?: number;
  height?: number;
}

export default function OutfitTryOnScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const baseUrl = getApiBaseUrl();

  const [sourceTab, setSourceTab] = useState<'wardrobe' | 'catalogue'>('wardrobe');

  // Portrait state
  const [latestPortrait, setLatestPortrait] = useState<PortraitInfo | null>(null);

  // Catalogue & Wardrobe state
  const [catalogueItems, setCatalogueItems] = useState<GarmentItem[]>([]);
  const [wardrobeItems, setWardrobeItems] = useState<GarmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Add dress modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newDressName, setNewDressName] = useState('');
  const [newDressCategory, setNewDressCategory] = useState<'top' | 'bottom' | 'overall' | 'outerwear'>('top');
  const [uploadingDress, setUploadingDress] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [catRes, wardRes, portraitRes] = await Promise.all([
        api.catalogue.list('outfit').catch(() => ({ items: [] })),
        api.wardrobe.list().catch(() => ({ items: [] })),
        api.upload.getLatest().catch(() => null),
      ]);

      if (portraitRes && portraitRes.url) {
        setLatestPortrait(portraitRes);
        session.ensureSession({ image_id: portraitRes.image_id, url: portraitRes.url });
      }

      const mappedCat: GarmentItem[] = (catRes.items ?? []).map((i: any) => ({
        id: i.item_id,
        name: i.name,
        category: i.subcategory ?? 'Outfit',
        color: i.color,
        imageUrl: i.thumbnail,
        isWardrobe: false}));

      const mappedWard: GarmentItem[] = (wardRes.items ?? []).map((w: any) => ({
        id: w.outfit_id,
        name: w.name,
        category: w.category,
        color: w.color,
        imageUrl: w.outfit_image,
        isWardrobe: true}));

      setCatalogueItems(mappedCat);
      setWardrobeItems(mappedWard);

      // Default selection to first wardrobe item if available
      if (mappedWard.length > 0) {
        setSelectedId((prev) => (prev ? prev : mappedWard[0].id));
      } else if (mappedCat.length > 0) {
        setSelectedId((prev) => (prev ? prev : mappedCat[0].id));
      }
    } catch (err: any) {
      setError(err.message || 'Could not load garments.');
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle deleting a wardrobe dress
  const handleDeleteDress = (item: GarmentItem) => {
    Alert.alert('Remove Garment', `Delete "${item.name}" from your digital wardrobe?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.wardrobe.delete(item.id);
            setWardrobeItems((prev) => prev.filter((w) => w.id !== item.id));
            if (selectedId === item.id) {
              setSelectedId(null);
            }
            Alert.alert('Removed', `"${item.name}" removed from your wardrobe.`);
          } catch (err: any) {
            Alert.alert('Delete Failed', err.message || 'Could not delete dress.');
          }
        }},
    ]);
  };

  // Handle uploading user's own dress
  const handlePickDressPhoto = async (useCamera: boolean = false) => {
    try {
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [3, 4],
        quality: 0.7};

      const result = useCamera
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setUploadingDress(true);
        const defaultName = `My ${newDressCategory.charAt(0).toUpperCase() + newDressCategory.slice(1)}`;
        const nameToUse = newDressName.trim() || defaultName;
        const res = await api.wardrobe.upload(
          asset.uri,
          nameToUse,
          newDressCategory,
          asset.mimeType || 'image/jpeg'
        );

        setShowAddModal(false);
        setNewDressName('');
        Alert.alert('Garment Added! ✨', `"${nameToUse}" has been added to your digital wardrobe.`);

        await loadData();
        setSelectedId(res.outfit_id);
      }
    } catch (err: any) {
      Alert.alert('Upload Failed', err.message || 'Could not upload garment.');
    } finally {
      setUploadingDress(false);
    }
  };

  type OutfitFilter = 'all' | 'tops' | 'bottoms' | 'outfits';
  const [catFilter, setCatFilter] = useState<OutfitFilter>('all');

  const currentList = sourceTab === 'wardrobe' ? wardrobeItems : catalogueItems;
  const filteredList = currentList.filter((item) => {
    if (catFilter === 'all') return true;
    const catLower = (item.category || '').toLowerCase();
    const nameLower = (item.name || '').toLowerCase();
    if (catFilter === 'tops') {
      return (
        catLower.includes('streetwear') ||
        catLower.includes('casual') ||
        catLower.includes('outerwear') ||
        catLower.includes('formal') ||
        catLower.includes('top') ||
        nameLower.includes('jacket') ||
        nameLower.includes('shirt') ||
        nameLower.includes('blazer') ||
        nameLower.includes('coat')
      );
    }
    if (catFilter === 'bottoms') {
      return (
        catLower.includes('bottom') ||
        catLower.includes('pant') ||
        catLower.includes('jean') ||
        catLower.includes('trouser') ||
        catLower.includes('skirt') ||
        nameLower.includes('jean') ||
        nameLower.includes('pant')
      );
    }
    if (catFilter === 'outfits') {
      return (
        catLower.includes('evening') ||
        catLower.includes('ethnic') ||
        catLower.includes('dress') ||
        catLower.includes('overall') ||
        nameLower.includes('gown') ||
        nameLower.includes('kurta') ||
        nameLower.includes('saree')
      );
    }
    return true;
  });

  const chosenGarment = currentList.find((g) => g.id === selectedId);

  // Effective source image: latest chained result if a styling session is active
  const sourceImage = session.current ??
    (latestPortrait ? { image_id: latestPortrait.image_id, url: latestPortrait.url } : null);
  const appliedStageCount = Object.keys(session.stages).length;
  const isChainedSource = Boolean(session.current && session.stages.outfit?.resultImageId !== session.current.image_id);

  const handleTryOn = async () => {
    if (!selectedId) {
      Alert.alert('Select a Garment', 'Please select a clothing item from your collection or catalogue.');
      return;
    }
    if (!sourceImage) {
      Alert.alert('Portrait Required', 'Please upload your portrait photo first.');
      return;
    }

    const personIdToUse = sourceImage.image_id;

    let clothType: string = 'upper';
    const catLower = (chosenGarment?.category || '').toLowerCase();
    const nameLower = (chosenGarment?.name || '').toLowerCase();
    if (
      catLower.includes('bottom') ||
      catLower.includes('pant') ||
      catLower.includes('jean') ||
      catLower.includes('trouser') ||
      catLower.includes('skirt') ||
      nameLower.includes('jean') ||
      nameLower.includes('pant')
    ) {
      clothType = 'lower';
    } else if (
      catLower.includes('evening') ||
      catLower.includes('ethnic') ||
      catLower.includes('overall') ||
      catLower.includes('dress') ||
      nameLower.includes('gown') ||
      nameLower.includes('kurta') ||
      nameLower.includes('saree')
    ) {
      clothType = 'overall';
    }

    setIsProcessing(true);
    try {
      const res = await api.tryon.outfit(
        personIdToUse,
        selectedId,
        sourceTab === 'wardrobe' ? 'wardrobe' : 'catalogue',
        chosenGarment?.category,
        clothType
      );

      if (res.status === 'failed') {
        Alert.alert('Try-On Failed', res.error || 'Could not synthesize this outfit. Please try again.');
        return;
      }

      session.setSelection('outfit', { itemId: selectedId, name: chosenGarment?.name });
      session.applyStageResult({
        stage: 'outfit',
        tryonId: res.tryon_id,
        resultImageId: res.result_image_id ?? null,
        resultUrl: res.result_image_url ?? '',
        sourceUrl: res.original_image_url ?? sourceImage.url,
        title: chosenGarment?.name ?? 'Virtual Outfit Try-On',
        style: `${sourceTab === 'wardrobe' ? 'My Wardrobe' : 'Store Collection'} • ${chosenGarment?.category ?? 'Garment'}`,
        mode: res.mode,
        appliedAt: Date.now(),
      });

      router.push({
        pathname: '/result',
        params: {
          category: 'outfit',
          title: chosenGarment?.name ?? 'Virtual Outfit Try-On',
          style: `${sourceTab === 'wardrobe' ? 'My Wardrobe' : 'Store Collection'} • ${chosenGarment?.category ?? 'Garment'}`,
          itemId: selectedId,
          tryonId: res.tryon_id,
          mode: res.mode,
          resultUrl: res.result_image_url ?? '',
          originalUrl: res.original_image_url ?? ''}});
    } catch (err: any) {
      Alert.alert('Try-On Error', err.message || 'Could not process try-on request.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>

        {/* Engine Banner */}
        <Card style={styles.engineCard} variant="flat">
          <View style={styles.engineRow}>
            <Text style={styles.engineIcon}>👗</Text>
            <View style={styles.engineInfo}>
              <Text style={styles.engineTitle}>Virtual Digital Wardrobe & Try-On</Text>
              <Text style={styles.engineDesc}>
                Photograph clothes you own or browse store styles to try them on virtually without dressing up physically!
              </Text>
            </View>
            <Badge label="AI Closet" variant="primary" />
          </View>
        </Card>

        {/* Photo Upload Prompt / Active Portrait */}
        <Text style={styles.sectionHeading}>1. Your Full-Body Portrait</Text>
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
                    label={isChainedSource ? `${appliedStageCount} Stage${appliedStageCount > 1 ? 's' : ''} Applied` : 'Validated'}
                    variant={isChainedSource ? 'primary' : 'success'}
                  />
                </View>
                <Text style={styles.photoDesc}>
                  {isChainedSource
                    ? 'The new outfit will replace the clothing on your latest styled look.'
                    : 'Tap to change or take a new portrait'}
                </Text>
              </View>
              <Text style={styles.photoChevron}>🔄</Text>
            </View>
          ) : (
            <View style={styles.portraitRow}>
              <Text style={styles.photoIcon}>📷</Text>
              <View style={styles.photoTextWrap}>
                <Text style={styles.photoTitle}>Upload Your Full-Body Photo</Text>
                <Text style={styles.photoDesc}>A full-length photo gives the best dress-fitting results.</Text>
              </View>
              <Text style={styles.photoChevron}>→</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Garment Source Switcher */}
        <Text style={styles.sectionHeading}>2. Select Clothing Source</Text>
        <View style={styles.sourceTabBar}>
          <TouchableOpacity
            style={[styles.sourceTabBtn, sourceTab === 'wardrobe' && styles.sourceTabBtnActive]}
            onPress={() => {
              setSourceTab('wardrobe');
              if (wardrobeItems.length > 0) setSelectedId(wardrobeItems[0].id);
            }}
          >
            <Text style={[styles.sourceTabText, sourceTab === 'wardrobe' && styles.sourceTabTextActive]}>
              👗 My Wardrobe ({wardrobeItems.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.sourceTabBtn, sourceTab === 'catalogue' && styles.sourceTabBtnActive]}
            onPress={() => {
              setSourceTab('catalogue');
              if (catalogueItems.length > 0) setSelectedId(catalogueItems[0].id);
            }}
          >
            <Text style={[styles.sourceTabText, sourceTab === 'catalogue' && styles.sourceTabTextActive]}>
              🛍️ Store Styles ({catalogueItems.length})
            </Text>
          </TouchableOpacity>
        </View>

        {/* Category Filter Chips */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.filterPillsScroll}
          contentContainerStyle={styles.filterPillsRow}
        >
          {[
            { id: 'all', label: 'All Items' },
            { id: 'tops', label: '🧥 Tops & Jackets' },
            { id: 'bottoms', label: '👖 Jeans & Bottoms' },
            { id: 'outfits', label: '👗 Dresses & Ethnic' },
          ].map((pill) => {
            const active = catFilter === pill.id;
            return (
              <TouchableOpacity
                key={pill.id}
                style={[styles.filterPill, active && styles.filterPillActive]}
                onPress={() => {
                  setCatFilter(pill.id as any);
                  const inCategory = currentList.filter((item) => {
                    if (pill.id === 'all') return true;
                    const catLower = (item.category || '').toLowerCase();
                    const nameLower = (item.name || '').toLowerCase();
                    if (pill.id === 'tops') return catLower.includes('streetwear') || catLower.includes('casual') || catLower.includes('outerwear') || catLower.includes('formal') || catLower.includes('top') || nameLower.includes('jacket') || nameLower.includes('shirt') || nameLower.includes('blazer');
                    if (pill.id === 'bottoms') return catLower.includes('bottom') || catLower.includes('pant') || catLower.includes('jean') || nameLower.includes('jean');
                    if (pill.id === 'outfits') return catLower.includes('evening') || catLower.includes('ethnic') || catLower.includes('dress') || nameLower.includes('gown') || nameLower.includes('kurta');
                    return true;
                  });
                  if (inCategory.length > 0 && !inCategory.some((i) => i.id === selectedId)) {
                    setSelectedId(inCategory[0].id);
                  }
                }}
              >
                <Text style={[styles.filterPillText, active && styles.filterPillTextActive]}>
                  {pill.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Action Button to add dress if on wardrobe tab */}
        {sourceTab === 'wardrobe' && (
          <TouchableOpacity
            style={styles.addDressBtn}
            onPress={() => setShowAddModal(true)}
            activeOpacity={0.8}
          >
            <Text style={styles.addDressIcon}>📸</Text>
            <View style={styles.addDressTextWrap}>
              <Text style={styles.addDressTitle}>+ Photograph Your Own Clothes</Text>
              <Text style={styles.addDressSub}>Take a picture of your shirt, jacket, pants, or outfit</Text>
            </View>
          </TouchableOpacity>
        )}

        {/* Garment Grid */}
        {loading && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Loading clothes collection...</Text>
          </View>
        )}

        {!loading && error && <ErrorMessage message={error} onRetry={loadData} />}

        {!loading && !error && filteredList.length === 0 && (
          <View style={styles.emptyWrap}>
            <Text style={styles.emptyIcon}>👗</Text>
            <Text style={styles.emptyText}>
              {sourceTab === 'wardrobe'
                ? 'No items found in this wardrobe category. Tap above to photograph clothes!'
                : 'No catalogue styles available in this category.'}
            </Text>
          </View>
        )}

        {!loading && !error && filteredList.length > 0 && (
          <View style={styles.catalogueGrid}>
            {filteredList.map((item) => {
              const isSelected = item.id === selectedId;
              const hasRealPhoto = item.imageUrl && item.imageUrl.length > 0;
              const photoUri = hasRealPhoto
                ? item.imageUrl!.startsWith('http')
                  ? item.imageUrl!
                  : `${baseUrl}${item.imageUrl}`
                : null;

              return (
                <TouchableOpacity
                  key={item.id}
                  style={[styles.garmentCard, isSelected && styles.garmentCardSelected]}
                  onPress={() => setSelectedId(item.id)}
                  activeOpacity={0.7}
                >
                  {/* Delete button for user wardrobe items */}
                  {item.isWardrobe && (
                    <TouchableOpacity
                      style={styles.deleteWardrobeBtn}
                      onPress={(e) => {
                        e.stopPropagation();
                        handleDeleteDress(item);
                      }}
                    >
                      <Text style={styles.deleteWardrobeText}>✕</Text>
                    </TouchableOpacity>
                  )}

                  {/* Real Photo Thumbnail or Color Dot + Emoji */}
                  {photoUri ? (
                    <Image source={{ uri: photoUri }} style={styles.garmentPhoto} resizeMode="contain" />
                  ) : (
                    <View style={styles.garmentPlaceholderWrap}>
                      <View style={[styles.colorDot, { backgroundColor: item.color ?? Colors.primary }]} />
                      <Text style={styles.garmentEmoji}>
                        {item.category.toLowerCase().includes('dress') ? '👗' : '👚'}
                      </Text>
                    </View>
                  )}

                  <Text style={styles.garmentName} numberOfLines={2}>
                    {item.name}
                  </Text>
                  <Text style={styles.garmentSub}>{item.category}</Text>

                  {isSelected && (
                    <View style={styles.selectedTick}>
                      <Text style={styles.selectedTickText}>✓</Text>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Selected Dress Info Card */}
        {chosenGarment && (
          <Card style={styles.descCard} variant="outlined">
            <View style={styles.descHeader}>
              <Text style={styles.descTitle}>{chosenGarment.name}</Text>
              <Badge
                label={chosenGarment.isWardrobe ? 'My Closet' : 'Catalogue'}
                variant={chosenGarment.isWardrobe ? 'success' : 'primary'}
              />
            </View>
            <Text style={styles.descSub}>Category: {chosenGarment.category}</Text>
          </Card>
        )}

        {/* Try-On Execution Button */}
        <Button
          title={
            isProcessing
              ? 'Warping & Fitting Garment...'
              : sourceTab === 'wardrobe'
              ? 'Try On My Dress ✨'
              : 'Try On Style ✨'
          }
          variant="primary"
          size="lg"
          loading={isProcessing}
          disabled={!selectedId || loading}
          onPress={handleTryOn}
          style={styles.tryOnBtn}
        />

        <Text style={styles.disclaimer}>
          * Digital wardrobe try-on fits your photographed clothes onto your body photo without changing physically!
        </Text>
      </ScrollView>

      {/* Add Dress Modal */}
      <Modal visible={showAddModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <Card style={styles.modalCard} variant="elevated">
            <Text style={styles.modalTitle}>Add to My Wardrobe ✨</Text>
            <Text style={styles.modalSubtitle}>
              Photograph a shirt, jacket, trousers, or overall outfit from your closet.
            </Text>

            <Text style={styles.inputLabel}>Garment Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. My Casual Button Shirt"
              placeholderTextColor={Colors.textMuted}
              value={newDressName}
              onChangeText={setNewDressName}
            />

            <Text style={styles.inputLabel}>Category</Text>
            <View style={styles.modalCatRow}>
              {(['top', 'bottom', 'overall', 'outerwear'] as const).map((cat) => {
                const active = newDressCategory === cat;
                return (
                  <TouchableOpacity
                    key={cat}
                    style={[styles.modalCatBtn, active && styles.modalCatBtnActive]}
                    onPress={() => setNewDressCategory(cat)}
                  >
                    <Text style={[styles.modalCatText, active && styles.modalCatTextActive]}>
                      {cat.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {uploadingDress ? (
              <View style={styles.modalLoading}>
                <ActivityIndicator size="large" color={Colors.primary} />
                <Text style={styles.modalLoadingText}>Saving garment to wardrobe...</Text>
              </View>
            ) : (
              <View style={styles.modalActions}>
                <Button
                  title="📷 Take Photo"
                  variant="primary"
                  size="md"
                  onPress={() => handlePickDressPhoto(true)}
                  style={styles.modalActionBtn}
                />
                <Button
                  title="🖼️ Gallery"
                  variant="outline"
                  size="md"
                  onPress={() => handlePickDressPhoto(false)}
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
  engineRow: { flexDirection: 'row', alignItems: 'center' },
  engineIcon: { fontSize: 28, marginRight: Spacing.md },
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
    alignItems: 'center'},
  portraitThumb: {
    width: 52,
    height: 52,
    borderRadius: BorderRadius.md,
    marginRight: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.primary},
  photoIcon: { fontSize: 28, marginRight: Spacing.md },
  photoTextWrap: { flex: 1 },
  validatedBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginBottom: 2},
  photoTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight},
  photoDesc: { fontSize: Typography.sizes.xs, color: Colors.textMuted, marginTop: 2 },
  photoChevron: { fontSize: 20, color: Colors.primaryLight },
  sourceTabBar: {
    flexDirection: 'row',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: 4,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border},
  sourceTabBtn: {
    flex: 1,
    paddingVertical: Spacing.sm + 2,
    alignItems: 'center',
    borderRadius: BorderRadius.sm},
  sourceTabBtnActive: {
    backgroundColor: Colors.primary},
  sourceTabText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium},
  sourceTabTextActive: {
    color: Colors.textInverse,
    fontWeight: Typography.weights.bold},
  filterPillsScroll: {
    marginBottom: Spacing.md,
  },
  filterPillsRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  filterPill: {
    paddingHorizontal: Spacing.sm + 4,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  filterPillActive: {
    backgroundColor: Colors.primaryGlow,
    borderColor: Colors.primary,
  },
  filterPillText: {
    fontSize: 11,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium,
  },
  filterPillTextActive: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
  },
  addDressBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.success,
    padding: Spacing.md,
    marginBottom: Spacing.lg},
  addDressIcon: { fontSize: 24, marginRight: Spacing.md },
  addDressTextWrap: { flex: 1 },
  addDressTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.success},
  addDressSub: { fontSize: 10, color: Colors.textMuted, marginTop: 2 },
  loadingWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  loadingText: { color: Colors.textMuted, fontSize: Typography.sizes.xs, marginTop: Spacing.sm },
  emptyWrap: { alignItems: 'center', paddingVertical: Spacing.xxl },
  emptyIcon: { fontSize: 40, marginBottom: Spacing.sm },
  emptyText: { color: Colors.textMuted, fontSize: Typography.sizes.xs, textAlign: 'center', paddingHorizontal: Spacing.lg },
  catalogueGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginBottom: Spacing.lg},
  garmentCard: {
    width: '47%',
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.md,
    borderWidth: 2,
    borderColor: Colors.border,
    padding: Spacing.md,
    alignItems: 'center',
    position: 'relative',
    overflow: 'hidden'},
  garmentCardSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primaryGlow},
  deleteWardrobeBtn: {
    position: 'absolute',
    top: 6,
    left: 6,
    zIndex: 10,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center'},
  deleteWardrobeText: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: 'bold'},
  garmentPhoto: {
    width: '100%',
    height: 100,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.xs,
    backgroundColor: Colors.surface},
  garmentPlaceholderWrap: {
    alignItems: 'center',
    marginBottom: Spacing.xs},
  colorDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    marginBottom: 4,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.2)'},
  garmentEmoji: { fontSize: 26 },
  garmentName: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    textAlign: 'center'},
  garmentSub: {
    fontSize: 10,
    color: Colors.textMuted,
    marginTop: 2,
    textTransform: 'capitalize'},
  selectedTick: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center'},
  selectedTickText: { color: Colors.textInverse, fontSize: 12, fontWeight: '800' },
  descCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.md,
    marginBottom: Spacing.lg},
  descHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4},
  descTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary},
  descSub: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    textTransform: 'capitalize'},
  tryOnBtn: { marginTop: Spacing.sm },
  disclaimer: {
    fontSize: 10,
    color: Colors.textMuted,
    textAlign: 'center',
    marginTop: Spacing.md,
    fontStyle: 'italic'},
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    padding: Spacing.xl},
  modalCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.xl,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.primary},
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
    backgroundColor: Colors.primaryGlow,
    borderColor: Colors.primary},
  modalCatText: {
    fontSize: 10,
    color: Colors.textMuted,
    fontWeight: Typography.weights.bold},
  modalCatTextActive: {
    color: Colors.primaryLight},
  modalActions: {
    gap: Spacing.sm},
  modalActionBtn: {
    width: '100%'},
  modalLoading: {
    alignItems: 'center',
    paddingVertical: Spacing.lg},
  modalLoadingText: {
    color: Colors.textMuted,
    fontSize: Typography.sizes.xs,
    marginTop: Spacing.sm}});
