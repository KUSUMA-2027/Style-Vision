import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  Alert} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Colors, Spacing, BorderRadius, Typography } from '@/constants/theme';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { api, saveAuthToken } from '@/services/api';

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert('Required Fields', 'Please enter your email and password.');
      return;
    }

    try {
      setLoading(true);
      const res = await api.auth.login(email.trim(), password);
      if (res.access_token) {
        await saveAuthToken(res.access_token);
        Alert.alert(
          'Welcome Back! ✨',
          `Signed in as ${res.user.name} (${res.user.email}).`,
          [{ text: 'Continue', onPress: () => router.replace('/') }]
        );
      }
    } catch (error: any) {
      Alert.alert(
        'Sign In Failed',
        error.message || 'Unable to sign in. Please verify your email and password.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <View style={styles.header}>
          <Text style={styles.logo}>👑</Text>
          <Text style={styles.title}>VIP Atelier Entrance</Text>
          <Text style={styles.subtitle}>Enter your credentials for bespoke couture access</Text>
        </View>

        <Card style={styles.card} variant="elevated">
          <Text style={styles.label}>Email Address</Text>
          <TextInput
            style={styles.input}
            placeholder="vip@stylevision.atelier"
            placeholderTextColor={Colors.textMuted}
            keyboardType="email-address"
            autoCapitalize="none"
            value={email}
            onChangeText={setEmail}
          />

          <Text style={styles.label}>Password</Text>
          <TextInput
            style={styles.input}
            placeholder="••••••••"
            placeholderTextColor={Colors.textMuted}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          <Button
            title="Enter Atelier"
            variant="primary"
            size="lg"
            loading={loading}
            onPress={handleLogin}
            style={styles.submitBtn}
          />

          <TouchableOpacity
            style={styles.demoBtn}
            onPress={() => {
              setEmail('demo@stylevision.com');
              setPassword('DemoPassword123');
            }}
          >
            <Text style={styles.demoText}>Use demo account (demo@stylevision.com)</Text>
          </TouchableOpacity>

          <View style={styles.footerRow}>
            <Text style={styles.footerText}>Not yet a member? </Text>
            <TouchableOpacity onPress={() => router.push('/(auth)/register')}>
              <Text style={styles.linkText}>Join Haute Atelier</Text>
            </TouchableOpacity>
          </View>
        </Card>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Colors.background},
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: Spacing.xl},
  header: {
    alignItems: 'center',
    marginBottom: Spacing.xxl},
  logo: {
    fontSize: 48,
    marginBottom: Spacing.sm},
  title: {
    fontSize: Typography.sizes.xl,
    fontWeight: Typography.weights.heavy,
    color: Colors.textPrimary,
    marginBottom: 4},
  subtitle: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted},
  card: {
    backgroundColor: Colors.surfaceCard,
    padding: Spacing.xxl,
    borderWidth: 1,
    borderColor: Colors.borderLight},
  label: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.textSecondary,
    marginBottom: Spacing.xs,
    textTransform: 'uppercase',
    letterSpacing: 0.5},
  input: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    color: Colors.textPrimary,
    fontSize: Typography.sizes.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.lg},
  submitBtn: {
    marginTop: Spacing.sm,
    marginBottom: Spacing.md},
  demoBtn: {
    alignItems: 'center',
    marginBottom: Spacing.md,
    paddingVertical: Spacing.sm},
  demoText: {
    fontSize: Typography.sizes.xs,
    color: Colors.primaryLight,
    textDecorationLine: 'underline'},
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'center'},
  footerText: {
    fontSize: Typography.sizes.xs,
    color: Colors.textMuted},
  linkText: {
    fontSize: Typography.sizes.xs,
    fontWeight: Typography.weights.bold,
    color: Colors.primaryLight}});
