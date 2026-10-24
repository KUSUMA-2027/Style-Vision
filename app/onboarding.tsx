import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, Typography, Shadows } from '@/constants/theme';
import { Button } from '@/components/ui/Button';

export default function OnboardingScreen() {
  const router = useRouter();
  const [currentSlide, setCurrentSlide] = useState(0);

  const slides = [
    {
      emoji: '🏛️',
      title: "L'Atelier Haute Couture",
      desc: 'Your prestige virtual fashion house. Experience bespoke digital draping, fine jewelry styling, cosmetics, and coiffure.',
    },
    {
      emoji: '✨',
      title: 'Neural Wardrobe Fitting',
      desc: 'Powered by neural landmark calibration to dynamically fit, scale, and drape designer outfits onto your portrait silhouette.',
    },
    {
      emoji: '💎',
      title: 'Fine Jewelry & Beauty Salons',
      desc: 'Biometric facial mesh precision to anchor 18k jewelry, couture optics, custom cosmetics, and bespoke hairstyles.',
    },
  ];

  const handleNext = () => {
    if (currentSlide < slides.length - 1) {
      setCurrentSlide(currentSlide + 1);
    } else {
      router.replace('/');
    }
  };

  const slide = slides[currentSlide];

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* Skip button */}
        <TouchableOpacity
          onPress={() => router.replace('/')}
          style={styles.skipButton}
        >
          <Text style={styles.skipText}>Skip</Text>
        </TouchableOpacity>

        {/* Slide Content */}
        <View style={styles.slideContent}>
          <View style={styles.emojiCircle}>
            <Text style={styles.emoji}>{slide.emoji}</Text>
          </View>
          <Text style={styles.title}>{slide.title}</Text>
          <Text style={styles.desc}>{slide.desc}</Text>
        </View>

        {/* Dots indicator */}
        <View style={styles.dotsRow}>
          {slides.map((_, index) => (
            <View
              key={index}
              style={[
                styles.dot,
                currentSlide === index && styles.dotActive,
              ]}
            />
          ))}
        </View>

        {/* Bottom Actions */}
        <View style={styles.actions}>
          <Button
            title={currentSlide === slides.length - 1 ? 'Get Started ✨' : 'Continue →'}
            variant="primary"
            size="lg"
            onPress={handleNext}
            style={styles.mainBtn}
          />
          <TouchableOpacity
            onPress={() => router.push('/(auth)/login')}
            style={styles.loginLink}
          >
            <Text style={styles.loginText}>
              Already have an account? <Text style={styles.loginBold}>Sign In</Text>
            </Text>
          </TouchableOpacity>
        </View>
      </View>
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
    padding: Spacing.xl,
    justifyContent: 'space-between',
  },
  skipButton: {
    alignSelf: 'flex-end',
    padding: Spacing.sm,
  },
  skipText: {
    color: Colors.textMuted,
    fontSize: Typography.sizes.sm,
    fontWeight: Typography.weights.medium,
  },
  slideContent: {
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
  },
  emojiCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: Colors.surface,
    borderWidth: 2,
    borderColor: Colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.xxl,
    ...Shadows.glow,
  },
  emoji: {
    fontSize: 56,
  },
  title: {
    fontSize: Typography.sizes.xxl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
    textAlign: 'center',
    marginBottom: Spacing.md,
  },
  desc: {
    fontSize: Typography.sizes.sm,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.border,
  },
  dotActive: {
    width: 24,
    backgroundColor: Colors.primary,
  },
  actions: {
    gap: Spacing.md,
    marginBottom: Spacing.lg,
  },
  mainBtn: {
    alignSelf: 'stretch',
  },
  loginLink: {
    alignItems: 'center',
    paddingVertical: Spacing.xs,
  },
  loginText: {
    color: Colors.textMuted,
    fontSize: Typography.sizes.xs,
  },
  loginBold: {
    color: Colors.primaryLight,
    fontWeight: Typography.weights.bold,
  },
});
