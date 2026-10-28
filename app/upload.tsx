import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Header } from '@/components/ui/Header';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PhotoPicker, UploadedPhotoData } from '@/components/photo/PhotoPicker';
import { useStylingSession } from '@/services/session';

export default function UploadScreen() {
  const router = useRouter();
  const session = useStylingSession();
  const [uploadedPhoto, setUploadedPhoto] = useState<UploadedPhotoData | null>(null);

  const handleContinue = () => {
    if (!uploadedPhoto) {
      Alert.alert('Photo Required', 'Please upload and validate a portrait before proceeding.');
      return;
    }
    // Navigate back to virtual styling studio
    router.replace('/(tabs)/try-on');
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Header title="Atelier Portrait Studio" showBack />

      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        {/* Portrait Guidelines Card */}
        <Card style={styles.tipsCard} variant="outlined">
          <Text style={styles.tipsTitle}>✨ Portrait Photo Tips</Text>
          <View style={styles.tipsList}>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Lighting & Pose:</Text> Bright, even lighting facing directly forward.</Text>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Fitting:</Text> Upper-body or full-body portrait with clear posture.</Text>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Crop Framing:</Text> Ensure your portrait is centered and fully visible inside the crop box.</Text>
          </View>
        </Card>

        {/* Interactive Photo Picker */}
        <PhotoPicker
          onPhotoUploaded={(data) => {
            setUploadedPhoto(data);
            // A fresh portrait always starts a new styling session chain
            session.startSession({ image_id: data.image_id, url: data.url });
          }}
        />

        {/* Action to proceed */}
        <Button
          title={uploadedPhoto ? "Proceed to Fitting ✨" : "Upload Portrait to Begin"}
          variant="primary"
          size="lg"
          disabled={!uploadedPhoto}
          onPress={handleContinue}
          style={styles.continueBtn}
        />
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
    padding: Spacing.lg,
    paddingBottom: Spacing.xxxl * 2,
  },
  tipsCard: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
  },
  tipsTitle: {
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.bold,
    color: Colors.accentGold,
    marginBottom: Spacing.xs,
  },
  tipsList: {
    gap: 4,
  },
  tipItem: {
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    lineHeight: 18,
  },
  tipBold: {
    color: Colors.textPrimary,
    fontWeight: Typography.weights.bold,
  },
  continueBtn: {
    marginTop: Spacing.lg,
  },
  cropNoticeBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(229, 169, 60, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(229, 169, 60, 0.35)',
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm + 2,
    marginBottom: Spacing.xs,
    gap: Spacing.sm,
  },
  cropNoticeIcon: {
    fontSize: 16,
  },
  cropNoticeText: {
    flex: 1,
    fontSize: Typography.sizes.xs,
    color: Colors.textSecondary,
    lineHeight: 18,
  },
  cropNoticeBold: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
  },
});
