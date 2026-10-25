/**
 * StyleVision — Media Save/Share Helpers
 * Uses lazy require() so a missing native module (e.g. Expo Go or an outdated
 * dev-client APK that predates expo-media-library) can never crash the route
 * bundle. Degrades gracefully: save to gallery → share sheet → open in browser.
 */
import { Platform, Linking } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';

// Literal-string lazy requires: Metro can bundle them statically, while the
// try/catch absorbs the "Cannot find native module" error on builds/Expo Go
// sessions that predate the native module.
function getMediaLibraryLegacy(): any | null {
  try {
    return require('expo-media-library/legacy');
  } catch {
    return null;
  }
}

function getMediaLibrary(): any | null {
  try {
    return require('expo-media-library');
  } catch {
    return null;
  }
}

function getSharing(): any | null {
  try {
    return require('expo-sharing');
  } catch {
    return null;
  }
}

async function shareOrOpen(url: string, filename: string): Promise<void> {
  const Sharing = getSharing();
  try {
    if (Sharing && typeof Sharing.isAvailableAsync === 'function' && (await Sharing.isAvailableAsync())) {
      const download = await FileSystem.downloadAsync(url, `${FileSystem.cacheDirectory}${filename}`);
      await Sharing.shareAsync(download.uri, { mimeType: 'image/png' });
      return;
    }
  } catch {
    // fall through to opening the URL
  }
  Linking.openURL(url).catch(() => {});
}

export interface SaveResult {
  ok: boolean;
  message: string;
}

/** Download an image and store it in the device photo library. */
export async function downloadImageToLibrary(url: string, filename: string): Promise<SaveResult> {
  if (Platform.OS === 'web') {
    window.open(url, '_blank');
    return { ok: true, message: 'Opened image in a new tab.' };
  }

  const legacy = getMediaLibraryLegacy();
  const next = getMediaLibrary();
  const MediaLibrary = legacy || next;

  if (!MediaLibrary) {
    // Native module not present in this build — degrade to share/open
    await shareOrOpen(url, filename);
    return {
      ok: false,
      message: 'Gallery saving is unavailable in this app build — opened the share sheet instead. Rebuild the app (npx expo run:android) to enable gallery download.',
    };
  }

  try {
    const requestPerms = legacy?.requestPermissionsAsync || next?.requestPermissionsAsync;
    if (typeof requestPerms === 'function') {
      const perm = await requestPerms();
      if (!perm?.granted) {
        return { ok: false, message: 'Photo library permission was denied.' };
      }
    }

    const download = await FileSystem.downloadAsync(url, `${FileSystem.cacheDirectory}${filename}`);

    // Try modern Asset.create() first, then fallback to legacy saveToLibraryAsync
    if (next?.Asset && typeof next.Asset.create === 'function') {
      await next.Asset.create(download.uri);
    } else if (legacy && typeof legacy.saveToLibraryAsync === 'function') {
      await legacy.saveToLibraryAsync(download.uri);
    } else if (legacy && typeof legacy.createAssetAsync === 'function') {
      await legacy.createAssetAsync(download.uri);
    } else {
      await shareOrOpen(url, filename);
      return { ok: false, message: 'Saved via share sheet.' };
    }

    return { ok: true, message: 'Your look has been saved to your photo library.' };
  } catch (err: any) {
    return { ok: false, message: err?.message || 'Could not save the image right now.' };
  }
}

/** Share an image via the native share sheet (falls back to opening it). */
export async function shareImage(url: string, filename: string): Promise<void> {
  if (Platform.OS === 'web') {
    window.open(url, '_blank');
    return;
  }
  await shareOrOpen(url, filename);
}
