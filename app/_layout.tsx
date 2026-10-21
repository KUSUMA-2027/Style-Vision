/**
 * StyleVision — Root Layout (Expo Router)
 *
 * Defines the root navigation structure, wraps the app in the StylingSession
 * provider (continuous stage chaining), and gates routes behind authentication.
 */
import { useEffect, useState } from 'react';
import { Stack, useRouter, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import * as SplashScreen from 'expo-splash-screen';
import { View, ActivityIndicator } from 'react-native';

import { Colors } from '@/constants/theme';
import { StylingSessionProvider } from '@/services/session';
import { getAuthToken } from '@/services/api';

// Keep the splash screen visible while fonts or assets are loading
SplashScreen.preventAutoHideAsync();

const PUBLIC_ROUTES = ['/onboarding', '/(auth)/login', '/(auth)/register'];

export default function RootLayout() {
  const router = useRouter();
  const pathname = usePathname();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  // Authentication gate: unauthenticated users are routed to sign-in
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await getAuthToken();
        if (cancelled) return;
        const isPublic = PUBLIC_ROUTES.some((r) => pathname?.startsWith(r));
        if (!token && !isPublic) {
          router.replace('/(auth)/login');
        }
      } catch {
        // Storage unavailable — allow through rather than locking the user out
      } finally {
        if (!cancelled) setAuthChecked(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  const isPublic = PUBLIC_ROUTES.some((r) => pathname?.startsWith(r));

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: Colors.background }}>
      <StylingSessionProvider>
        <StatusBar style="light" />
        {!authChecked && !isPublic ? (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.background }}>
            <ActivityIndicator size="large" color={Colors.primary} />
          </View>
        ) : (
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: Colors.backgroundSecondary },
              headerTintColor: Colors.primary,
              headerTitleStyle: { fontWeight: '700' },
              headerShadowVisible: false,
              contentStyle: { backgroundColor: Colors.background },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="onboarding" options={{ headerShown: false }} />
            <Stack.Screen name="(auth)/login" options={{ title: 'VIP Atelier Sign In', presentation: 'modal' }} />
            <Stack.Screen name="(auth)/register" options={{ title: 'Join Exclusive Atelier', presentation: 'modal' }} />
            <Stack.Screen name="upload" options={{ title: 'Portrait Studio' }} />
            <Stack.Screen name="try-on/outfit" options={{ title: 'Haute Wardrobe Fitting' }} />
            <Stack.Screen name="try-on/accessories" options={{ title: 'Fine Jewelry & Optics' }} />
            <Stack.Screen name="try-on/makeup" options={{ title: 'Beauty & Cosmetics Atelier' }} />
            <Stack.Screen name="try-on/hairstyle" options={{ title: 'Haute Coiffure Salon' }} />
            <Stack.Screen name="result" options={{ title: 'Atelier Reveal & Export' }} />
            <Stack.Screen name="complete-look" options={{ title: 'The Complete Look' }} />
            <Stack.Screen name="admin/catalogue" options={{ title: 'Curator Catalogue Admin' }} />
          </Stack>
        )}
      </StylingSessionProvider>
    </GestureHandlerRootView>
  );
}
