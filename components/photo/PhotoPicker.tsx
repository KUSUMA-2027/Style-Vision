/**
 * StyleVision — Interactive Photo Picker Component
 * Supports selecting from device library or capturing via camera with live preview,
 * client-side checks, server-side suitability analysis, replace, and remove actions.
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { api } from '@/services/api';

export interface UploadedPhotoData {
  image_id: string;
  url: string;
  width?: number;
  height?: number;
  suitability_note?: string;
  quality_score?: string;
}

interface PhotoPickerProps {
  onPhotoSelected?: (uri: string) => void;
  onPhotoUploaded: (data: UploadedPhotoData) => void;
  initialPhotoUrl?: string;
}

export const PhotoPicker: React.FC<PhotoPickerProps> = ({
  onPhotoSelected,
  onPhotoUploaded,
  initialPhotoUrl,
}) => {
  const [localUri, setLocalUri] = useState<string | null>(null);
  const [uploadedData, setUploadedData] = useState<UploadedPhotoData | null>(
    initialPhotoUrl
      ? { image_id: 'default', url: initialPhotoUrl, suitability_note: 'Demo photo active' }
      : null
  );
  const [uploading, setUploading] = useState(false);

  // --- Pick from device gallery ---
  const handlePickLibrary = async () => {
    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          'Permission Needed',
          'Please allow access to your photo library to select a portrait for virtual try-on.'
        );
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [3, 4],
        quality: 0.9,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setLocalUri(asset.uri);
        setUploadedData(null);
        if (onPhotoSelected) onPhotoSelected(asset.uri);
        // Automatically start upload
        await uploadSelectedPhoto(asset.uri, asset.fileName || 'portrait.jpg', asset.mimeType || 'image/jpeg');
      }
    } catch (err: any) {
      Alert.alert('Selection Error', err.message || 'Could not select photo.');
    }
  };

  // --- Capture using device camera ---
  const handleLaunchCamera = async () => {
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert(
          'Camera Permission Needed',
          'Please allow camera access to take a portrait photo for virtual styling.'
        );
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: true,
        aspect: [3, 4],
        quality: 0.9,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setLocalUri(asset.uri);
        setUploadedData(null);
        if (onPhotoSelected) onPhotoSelected(asset.uri);
        await uploadSelectedPhoto(asset.uri, asset.fileName || 'camera_portrait.jpg', asset.mimeType || 'image/jpeg');
      }
    } catch (err: any) {
      Alert.alert('Camera Error', err.message || 'Could not open camera.');
    }
  };

  // --- Perform multipart upload & server validation ---
  const uploadSelectedPhoto = async (uri: string, filename: string, mimeType: string) => {
    setUploading(true);
    try {
      const data = await api.upload.uploadPhoto(uri, filename, mimeType);
      const photoPayload: UploadedPhotoData = {
        image_id: data.image_id,
        url: data.url,
        width: data.width,
        height: data.height,
        suitability_note: data.suitability_note,
        quality_score: data.quality_score,
      };
      setUploadedData(photoPayload);
      onPhotoUploaded(photoPayload);
    } catch (err: any) {
      Alert.alert(
        'Image Validation Error',
        err.message || 'The server could not accept this image. Please ensure it is a clear portrait.'
      );
    } finally {
      setUploading(false);
    }
  };

  // --- Remove photo ---
  const handleRemove = () => {
    setLocalUri(null);
    setUploadedData(null);
  };

  const currentDisplayUri = localUri || uploadedData?.url;

  return (
    <View style={styles.container}>
      {currentDisplayUri ? (
        // Preview State
        <View style={styles.previewContainer}>
          <Image source={{ uri: currentDisplayUri }} style={styles.previewImage} />

          {uploading && (
            <View style={styles.overlayLoading}>
              <ActivityIndicator size="large" color={Colors.primary} />
              <Text style={styles.uploadingText}>Validating & Uploading...</Text>
            </View>
          )}

          {uploadedData && !uploading && (
            <View style={styles.suitabilityCard}>
              <View style={styles.suitabilityHeader}>
                <Badge label="Validated for Try-On" variant="success" />
                {uploadedData.width && uploadedData.height && (
                  <Text style={styles.resolutionText}>
                    {uploadedData.width} × {uploadedData.height} px
                  </Text>
                )}
              </View>
              {uploadedData.suitability_note && (
                <Text style={styles.suitabilityNote}>{uploadedData.suitability_note}</Text>
              )}
            </View>
          )}

          {/* Action buttons */}
          <View style={styles.actionRow}>
            <Button
              title="Replace"
              variant="outline"
              size="sm"
              onPress={handlePickLibrary}
              disabled={uploading}
              style={styles.actionBtn}
            />
            <Button
              title="Camera"
              variant="outline"
              size="sm"
              onPress={handleLaunchCamera}
              disabled={uploading}
              style={styles.actionBtn}
            />
            <Button
              title="Remove"
              variant="ghost"
              size="sm"
              onPress={handleRemove}
              disabled={uploading}
              style={styles.actionBtn}
            />
          </View>
        </View>
      ) : (
        // Empty State / Upload trigger
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyIcon}>📸</Text>
          <Text style={styles.emptyTitle}>Upload Your Portrait</Text>
          <Text style={styles.emptyDesc}>
            Front-facing photo with good lighting and clear view of face and upper body.
          </Text>

          <View style={styles.buttonsRow}>
            <TouchableOpacity style={styles.pickButton} onPress={handlePickLibrary}>
              <Text style={styles.buttonIcon}>🖼️</Text>
              <Text style={styles.buttonLabel}>Photo Library</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.pickButton} onPress={handleLaunchCamera}>
              <Text style={styles.buttonIcon}>📷</Text>
              <Text style={styles.buttonLabel}>Take Photo</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.surfaceCard,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.borderLight,
    overflow: 'hidden',
    marginVertical: Spacing.md,
  },
  emptyContainer: {
    padding: Spacing.xxl,
    alignItems: 'center',
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: Spacing.sm,
  },
  emptyTitle: {
    fontSize: Typography.sizes.md,
    fontWeight: Typography.weights.bold,
    color: Colors.textPrimary,
    marginBottom: 4,
  },
  emptyDesc: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
    textAlign: 'center',
    marginBottom: Spacing.lg,
    lineHeight: 18,
  },
  buttonsRow: {
    flexDirection: 'row',
    gap: Spacing.md,
  },
  pickButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.sm,
  },
  buttonIcon: {
    fontSize: 18,
  },
  buttonLabel: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.medium,
    color: Colors.textPrimary,
  },
  previewContainer: {
    padding: Spacing.md,
  },
  previewImage: {
    width: '100%',
    height: 320,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.surface,
    resizeMode: 'cover',
  },
  overlayLoading: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: Colors.overlay,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: BorderRadius.md,
  },
  uploadingText: {
    color: Colors.textPrimary,
    fontSize: Typography.sizes.xs,
    marginTop: Spacing.sm,
    fontWeight: Typography.weights.medium,
  },
  suitabilityCard: {
    backgroundColor: Colors.surface,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  suitabilityHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  resolutionText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted,
  },
  suitabilityNote: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    lineHeight: 16,
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: Spacing.md,
    gap: Spacing.sm,
  },
  actionBtn: {
    flex: 1,
  },
});
