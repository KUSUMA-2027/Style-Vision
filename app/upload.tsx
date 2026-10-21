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
        {/* Quality Guidelines Card */}
        <Card style={styles.tipsCard} variant="outlined">
          <Text style={styles.tipsTitle}>👑 Haute Couture Portrait Guidelines</Text>
          <View style={styles.tipsList}>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Lighting:</Text> Bright, evenly-lit face without harsh shadows.</Text>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Pose:</Text> Facing directly toward the camera, neutral posture.</Text>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Background:</Text> Clean, uncluttered, or solid background works best.</Text>
            <Text style={styles.tipItem}>• <Text style={styles.tipBold}>Wardrobe Fitting:</Text> Upper-body portrait visible from waist up.</Text>
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
});
