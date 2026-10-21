import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorMessage } from '@/components/ui/ErrorMessage';
import { api } from '@/services/api';
import { TryOnCategory } from '@/types';

interface AdminStyleItem {
  item_id: string;
  name: string;
  category: TryOnCategory;
  subcategory?: string;
  description?: string;
  is_active: boolean;
}

export default function AdminCatalogueScreen() {
  const [activeCategory, setActiveCategory] = useState<'all' | TryOnCategory>('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newItemName, setNewItemName] = useState('');
  const [newItemCategory, setNewItemCategory] = useState<TryOnCategory>('outfit');
  const [newItemSubcat, setNewItemSubcat] = useState('');
  const [newItemDesc, setNewItemDesc] = useState('');

  const [items, setItems] = useState<AdminStyleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const catParam = activeCategory === 'all' ? undefined : activeCategory;
      const res = await api.catalogue.list(catParam);
      setItems(res.items ?? []);
    } catch (err: any) {
      setError(err.message || 'Could not load catalogue from MongoDB.');
    } finally {
      setLoading(false);
    }
  }, [activeCategory]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const toggleActive = async (item: AdminStyleItem) => {
    try {
      const updated = await api.admin.updateItem(item.item_id, {
        is_active: !item.is_active});
      setItems((prev) =>
        prev.map((i) => (i.item_id === item.item_id ? { ...i, is_active: updated.is_active } : i))
      );
    } catch (err: any) {
      Alert.alert('Update Failed', err.message || 'Could not update item status.');
    }
  };

  const deleteItem = (item_id: string, name: string) => {
    Alert.alert('Delete Style', `Permanently remove "${name}" from MongoDB catalogue?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.admin.deleteItem(item_id);
            setItems((prev) => prev.filter((i) => i.item_id !== item_id));
            Alert.alert('Deleted', `"${name}" removed from catalogue.`);
          } catch (err: any) {
            Alert.alert('Delete Error', err.message || 'Could not delete item.');
          }
        }},
    ]);
  };

  const handleAddItem = async () => {
    if (!newItemName.trim()) {
      Alert.alert('Required Field', 'Please enter a name for the style item.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: newItemName.trim(),
        category: newItemCategory,
        subcategory: newItemSubcat.trim() || undefined,
        description: newItemDesc.trim() || undefined,
        tags: [newItemCategory, newItemSubcat.toLowerCase().trim()].filter(Boolean),
        is_active: true};
      await api.admin.createItem(payload);
      setNewItemName('');
      setNewItemSubcat('');
      setNewItemDesc('');
      setShowAddForm(false);
      Alert.alert('Item Added ✨', `"${payload.name}" is now live in MongoDB catalogue!`);
      loadItems();
    } catch (err: any) {
      Alert.alert('Creation Failed', err.message || 'Could not add item to catalogue.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Catalogue Management</Text>
          <Text style={styles.subtitle}>
            Administrator module for managing available virtual styling garments, accessories & makeup
          </Text>
        </View>

        {/* Category Filter Pills */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {(
            [
              { key: 'all', label: 'All Items' },
              { key: 'outfit', label: 'Outfits' },
              { key: 'accessories', label: 'Accessories' },
              { key: 'makeup', label: 'Makeup' },
              { key: 'hairstyle', label: 'Hairstyles' },
            ] as const
          ).map((c) => {
            const active = activeCategory === c.key;
            return (
              <TouchableOpacity
                key={c.key}
                onPress={() => setActiveCategory(c.key)}
                style={[styles.pill, active && styles.pillActive]}
              >
                <Text style={[styles.pillText, active && styles.pillTextActive]}>
                  {c.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {/* Add Style Form Toggle / Form */}
        {showAddForm ? (
          <Card style={styles.addCard} variant="elevated">
            <Text style={styles.addTitle}>Add New Style Item</Text>

            <Text style={styles.inputLabel}>Category</Text>
            <View style={styles.categoryPickerRow}>
              {(['outfit', 'accessories', 'makeup', 'hairstyle'] as TryOnCategory[]).map((cat) => {
                const selected = newItemCategory === cat;
                return (
                  <TouchableOpacity
                    key={cat}
                    onPress={() => setNewItemCategory(cat)}
                    style={[styles.catPickBtn, selected && styles.catPickBtnActive]}
                  >
                    <Text style={[styles.catPickText, selected && styles.catPickTextActive]}>
                      {cat.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={styles.inputLabel}>Item Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Italian Wool Trench Coat"
              placeholderTextColor={Colors.textMuted}
              value={newItemName}
              onChangeText={setNewItemName}
            />

            <Text style={styles.inputLabel}>Subcategory / Tag</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Outerwear, glasses, lipstick..."
              placeholderTextColor={Colors.textMuted}
              value={newItemSubcat}
              onChangeText={setNewItemSubcat}
            />

            <Text style={styles.inputLabel}>Description</Text>
            <TextInput
              style={styles.input}
              placeholder="Material, styling fit, and texture details..."
              placeholderTextColor={Colors.textMuted}
              value={newItemDesc}
              onChangeText={setNewItemDesc}
            />

            <View style={styles.addActions}>
              <Button
                title={saving ? 'Saving...' : 'Save to MongoDB'}
                variant="primary"
                size="md"
                loading={saving}
                onPress={handleAddItem}
                style={styles.actionBtn}
              />
              <Button
                title="Cancel"
                variant="ghost"
                size="md"
                onPress={() => setShowAddForm(false)}
                style={styles.actionBtn}
              />
            </View>
          </Card>
        ) : (
          <Button
            title="+ Add New Style Item"
            variant="outline"
            size="md"
            onPress={() => setShowAddForm(true)}
            style={styles.addToggleBtn}
          />
        )}

        {/* Catalogue Items List */}
        <Text style={styles.sectionHeading}>
          Live MongoDB Items ({items.length})
        </Text>

        {loading && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.loadingText}>Fetching catalogue from database...</Text>
          </View>
        )}

        {!loading && error && (
          <ErrorMessage message={error} onRetry={loadItems} />
        )}

        {!loading && !error && items.length === 0 && (
          <View style={styles.emptyWrap}>
            <Text style={styles.emptyIcon}>📦</Text>
            <Text style={styles.emptyText}>No items found.</Text>
          </View>
        )}

        {!loading && !error && items.length > 0 && (
          <View style={styles.itemsList}>
            {items.map((item) => (
              <Card key={item.item_id} style={styles.itemCard} variant="flat">
                <View style={styles.itemRow}>
                  <View style={styles.itemInfo}>
                    <View style={styles.badgeRow}>
                      <Badge
                        label={item.category.toUpperCase()}
                        variant={item.category === 'outfit' ? 'primary' : 'success'}
                      />
                      {item.subcategory && (
                        <Text style={styles.subcatText}>• {item.subcategory}</Text>
                      )}
                    </View>
                    <Text style={styles.itemName}>{item.name}</Text>
                    {item.description && (
                      <Text style={styles.itemDesc} numberOfLines={1}>{item.description}</Text>
                    )}
                  </View>
                  <View style={styles.controlsRow}>
                    <TouchableOpacity
                      onPress={() => toggleActive(item)}
                      style={[styles.statusToggle, item.is_active && styles.statusToggleActive]}
                    >
                      <Text style={[styles.toggleText, item.is_active && styles.toggleTextActive]}>
                        {item.is_active ? 'ACTIVE' : 'HIDDEN'}
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={() => deleteItem(item.item_id, item.name)}
                      style={styles.deleteBtn}
                    >
                      <Text style={styles.deleteIcon}>🗑️</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              </Card>
            ))}
          </View>
        )}
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
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginTop: 4,
    lineHeight: 18},
  filterRow: {
    flexDirection: 'row',
    marginBottom: Spacing.xl},
  pill: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    marginRight: Spacing.sm},
  pillActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary},
  pillText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    fontWeight: Typography.weights.medium},
  pillTextActive: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold},
  addToggleBtn: {
    marginBottom: Spacing.xl},
  addCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.lg,
    marginBottom: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.primary},
  addTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: Spacing.md},
  inputLabel: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    marginBottom: 4,
    fontWeight: Typography.weights.medium},
  categoryPickerRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
    marginBottom: Spacing.md},
  catPickBtn: {
    flex: 1,
    paddingVertical: Spacing.xs,
    alignItems: 'center',
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border},
  catPickBtnActive: {
    backgroundColor: Colors.primaryGlow,
    borderColor: Colors.primary},
  catPickText: {
    fontSize: 10,
    color: Colors.textMuted,
    fontWeight: Typography.weights.bold},
  catPickTextActive: {
    color: Colors.primaryLight},
  input: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    color: Colors.textPrimary,
    fontSize: Typography.sizes.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.md},
  addActions: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.xs},
  actionBtn: {
    flex: 1},
  sectionHeading: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textSecondary,
    marginBottom: Spacing.md,
    textTransform: 'uppercase',
    letterSpacing: 0.5},
  loadingWrap: {
    alignItems: 'center',
    paddingVertical: Spacing.xxl},
  loadingText: {
    color: Colors.textMuted,
    fontSize: Typography.sizes.xs,
    marginTop: Spacing.sm},
  emptyWrap: {
    alignItems: 'center',
    paddingVertical: Spacing.xxl},
  emptyIcon: {
    fontSize: 40,
    marginBottom: Spacing.sm},
  emptyText: {
    color: Colors.textMuted,
    fontSize: Typography.sizes.sm},
  itemsList: {
    gap: Spacing.sm},
  itemCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border},
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'},
  itemInfo: {
    flex: 1,
    marginRight: Spacing.sm},
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4},
  subcatText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    marginLeft: Spacing.sm},
  itemName: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary},
  itemDesc: {
    fontSize: 10,
    color: Colors.textMuted,
    marginTop: 2},
  controlsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm},
  statusToggle: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
    backgroundColor: Colors.surfaceHover,
    borderWidth: 1,
    borderColor: Colors.border},
  statusToggleActive: {
    backgroundColor: Colors.successBg,
    borderColor: Colors.success},
  toggleText: {
    fontSize: 10,
    fontWeight: Typography.weights.bold,
    color: Colors.textMuted},
  toggleTextActive: {
    color: Colors.success},
  deleteBtn: {
    padding: Spacing.xs},
  deleteIcon: {
    fontSize: 16}});
