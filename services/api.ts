/**
 * StyleVision — Frontend API Client
 * Typed service connecting the React Native Expo app to the FastAPI backend.
 * Handles dynamic host resolution for both physical mobile devices and local web testing.
 */
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import * as FileSystem from 'expo-file-system/legacy';
import { TryOnCategory } from '@/types';

// Dynamic API URL resolver matching dev environment
export function getApiBaseUrl(): string {
  // 1. Browser check for web testing
  if (Platform.OS === 'web' && typeof window !== 'undefined' && window.location) {
    const hostname = window.location.hostname || 'localhost';
    return `http://${hostname}:8000`;
  }

  // 2. Auto-detect host IP from Expo bundler (dynamically matches current Wi-Fi)
  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    const hostIp = hostUri.split(':')[0];
    if (hostIp && hostIp !== 'localhost' && hostIp !== '127.0.0.1') {
      return `http://${hostIp}:8000`;
    }
  }

  // 3. Fall back to environment variable
  const envUrl = process.env.EXPO_PUBLIC_API_URL;
  if (envUrl && !envUrl.includes('localhost') && !envUrl.includes('127.0.0.1')) {
    return envUrl;
  }

  // 4. Default Wi-Fi IP / local fallback
  return 'http://192.168.29.173:8000';
}

const TOKEN_KEY = 'stylevision_jwt_token';

// ── Token Storage Helpers ─────────────────────────────────────────────────────

export async function saveAuthToken(token: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } catch {
    // Fallback for web where SecureStore might not be available
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(TOKEN_KEY, token);
    }
  }
}

export async function getAuthToken(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem(TOKEN_KEY);
    }
    return null;
  }
}

export async function removeAuthToken(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(TOKEN_KEY);
    }
  }
}

// ── Generic Request Wrapper ───────────────────────────────────────────────────

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const token = await getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errorJson = await response.json();
      if (typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson.detail)) {
        errorDetail = errorJson.detail
          .map((d: any) => (d.msg ? `${d.loc ? d.loc.join('.') + ': ' : ''}${d.msg}` : JSON.stringify(d)))
          .join(', ');
      } else if (errorJson.error) {
        errorDetail = errorJson.error;
      }
    } catch {
      // Body was not json
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

// ── API Namespace ─────────────────────────────────────────────────────────────

export const api = {
  // --- System ---
  health: () => request<{ status: string; app: string; version: string; tryon_mode: string }>('/health'),

  // --- Authentication ---
  auth: {
    register: (name: string, email: string, password: string) =>
      request<any>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      }),

    login: (email: string, password: string) =>
      request<any>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),

    getMe: () => request<any>('/api/v1/auth/me'),
  },

  // --- Photo Upload ---
  upload: {
    uploadPhoto: async (uri: string, filename: string, mimeType: string) => {
      const baseUrl = getApiBaseUrl();
      const token = await getAuthToken();

      if (Platform.OS === 'web') {
        const formData = new FormData();
        const response = await fetch(uri);
        const blob = await response.blob();
        formData.append('file', blob, filename);

        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${baseUrl}/api/v1/upload/photo`, {
          method: 'POST',
          body: formData,
          headers,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Upload failed with status ${res.status}`);
        }
        return res.json();
      }

      // Native (Android / iOS): Use FileSystem.uploadAsync
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const uploadResult = await FileSystem.uploadAsync(
        `${baseUrl}/api/v1/upload/photo`,
        uri,
        {
          fieldName: 'file',
          httpMethod: 'POST',
          uploadType: FileSystem.FileSystemUploadType.MULTIPART,
          headers,
        }
      );

      if (uploadResult.status < 200 || uploadResult.status >= 300) {
        let errorDetail = `Upload failed with status ${uploadResult.status}`;
        try {
          const parsed = JSON.parse(uploadResult.body);
          if (parsed.detail) errorDetail = parsed.detail;
          if (parsed.error) errorDetail = parsed.error;
        } catch (_) {}
        throw new Error(errorDetail);
      }

      return JSON.parse(uploadResult.body);
    },

    getLatest: () => request<any>('/api/v1/upload/latest'),
  },

  // --- Style Catalogue ---
  catalogue: {
    list: (category?: TryOnCategory) =>
      request<any>(category ? `/api/v1/catalogue?category=${category}` : '/api/v1/catalogue'),

    get: (itemId: string) => request<any>(`/api/v1/catalogue/${itemId}`),

    uploadAccessory: async (uri: string, name: string, subcategory: string = 'glasses', mimeType: string = 'image/png') => {
      const baseUrl = getApiBaseUrl();
      const token = await getAuthToken();

      if (Platform.OS === 'web') {
        const formData = new FormData();
        const response = await fetch(uri);
        const blob = await response.blob();
        formData.append('file', blob, `${name.replace(/\s+/g, '_').toLowerCase()}.png`);
        formData.append('name', name);
        formData.append('subcategory', subcategory);

        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${baseUrl}/api/v1/catalogue/upload-accessory`, {
          method: 'POST',
          body: formData,
          headers,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Upload failed with status ${res.status}`);
        }
        return res.json();
      }

      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const uploadResult = await FileSystem.uploadAsync(
        `${baseUrl}/api/v1/catalogue/upload-accessory`,
        uri,
        {
          fieldName: 'file',
          httpMethod: 'POST',
          uploadType: FileSystem.FileSystemUploadType.MULTIPART,
          parameters: {
            name,
            subcategory,
          },
          headers,
        }
      );

      if (uploadResult.status < 200 || uploadResult.status >= 300) {
        let errorDetail = `Upload failed with status ${uploadResult.status}`;
        try {
          const parsed = JSON.parse(uploadResult.body);
          if (parsed.detail) errorDetail = parsed.detail;
          if (parsed.error) errorDetail = parsed.error;
        } catch (_) {}
        throw new Error(errorDetail);
      }

      return JSON.parse(uploadResult.body);
    },
  },

  // --- Digital Wardrobe ("My Closet") ---
  wardrobe: {
    list: () => request<any>('/api/v1/wardrobe'),

    get: (outfitId: string) => request<any>(`/api/v1/wardrobe/${outfitId}`),

    upload: async (uri: string, name: string, category: string = 'top', mimeType: string = 'image/jpeg') => {
      const baseUrl = getApiBaseUrl();
      const token = await getAuthToken();

      if (Platform.OS === 'web') {
        const formData = new FormData();
        const response = await fetch(uri);
        const blob = await response.blob();
        formData.append('file', blob, `${name.replace(/\s+/g, '_').toLowerCase()}.jpg`);
        formData.append('name', name);
        formData.append('category', category);

        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${baseUrl}/api/v1/wardrobe/upload`, {
          method: 'POST',
          body: formData,
          headers,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Upload failed with status ${res.status}`);
        }
        return res.json();
      }

      // Native (Android / iOS): Use FileSystem.uploadAsync
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const uploadResult = await FileSystem.uploadAsync(
        `${baseUrl}/api/v1/wardrobe/upload`,
        uri,
        {
          fieldName: 'file',
          httpMethod: 'POST',
          uploadType: FileSystem.FileSystemUploadType.MULTIPART,
          parameters: {
            name,
            category,
          },
          headers,
        }
      );

      if (uploadResult.status < 200 || uploadResult.status >= 300) {
        let errorDetail = `Upload failed with status ${uploadResult.status}`;
        try {
          const parsed = JSON.parse(uploadResult.body);
          if (parsed.detail) errorDetail = parsed.detail;
          if (parsed.error) errorDetail = parsed.error;
        } catch (_) {}
        throw new Error(errorDetail);
      }

      return JSON.parse(uploadResult.body);
    },

    update: (
      outfitId: string,
      updates: { name?: string; category?: string; color?: string; notes?: string }
    ) =>
      request<any>(`/api/v1/wardrobe/${outfitId}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      }),

    delete: (outfitId: string) =>
      request<any>(`/api/v1/wardrobe/${outfitId}`, {
        method: 'DELETE',
      }),
  },

  // --- Virtual Try-On ---
  tryon: {
    outfit: (personImageId: string, garmentId: string, source: 'wardrobe' | 'catalogue' = 'catalogue', category?: string, clothType?: string) =>
      request<any>('/api/v1/tryon/outfit', {
        method: 'POST',
        body: JSON.stringify({
          person_image_id: personImageId,
          style_item_id: source === 'catalogue' ? garmentId : undefined,
          outfit_id: source === 'wardrobe' ? garmentId : undefined,
          source,
          category,
          cloth_type: clothType,
        }),
      }),

    accessories: (
      personImageId: string,
      styleItemId: string,
      subcategory: string,
      overrides?: { position_x?: number; position_y?: number; scale?: number }
    ) =>
      request<any>('/api/v1/tryon/accessories', {
        method: 'POST',
        body: JSON.stringify({
          person_image_id: personImageId,
          style_item_id: styleItemId,
          subcategory,
          ...overrides,
        }),
      }),

    makeup: (
      personImageId: string,
      makeupType: string,
      colorHex: string,
      intensity: number = 0.6,
      finish: string = 'satin'
    ) =>
      request<any>('/api/v1/tryon/makeup', {
        method: 'POST',
        body: JSON.stringify({
          person_image_id: personImageId,
          makeup_type: makeupType,
          color_hex: colorHex,
          intensity,
          finish,
        }),
      }),

    hairstyle: (personImageId: string, styleItemId: string, colorHex?: string) =>
      request<any>('/api/v1/tryon/hairstyle', {
        method: 'POST',
        body: JSON.stringify({
          person_image_id: personImageId,
          style_item_id: styleItemId,
          color_hex: colorHex,
        }),
      }),

    getStatus: (tryonId: string) => request<any>(`/api/v1/tryon/${tryonId}`),

    getChain: (imageId: string) => request<any>(`/api/v1/tryon/chain/${imageId}`),

    getSessionStages: (baseImageId: string) =>
      request<any>(`/api/v1/tryon/session/${baseImageId}/stages`),

    removeItem: (personImageId: string, stage: string, slotValue?: string) =>
      request<any>('/api/v1/tryon/remove', {
        method: 'POST',
        body: JSON.stringify({
          person_image_id: personImageId,
          stage,
          slot_value: slotValue,
        }),
      }),
  },

  // --- Saved Looks / History ---
  history: {
    list: (category?: TryOnCategory) =>
      request<any>(category ? `/api/v1/history?category=${category}` : '/api/v1/history'),

    get: (lookId: string) => request<any>(`/api/v1/history/${lookId}`),

    save: (
      tryonId: string,
      title?: string,
      sessionMeta?: { base_image_id?: string; final_image_id?: string; stages?: any[]; category?: string }
    ) =>
      request<any>('/api/v1/history/save', {
        method: 'POST',
        body: JSON.stringify({
          tryon_id: tryonId,
          title,
          ...(sessionMeta || {}),
        }),
      }),

    update: (lookId: string, updates: { title?: string }) =>
      request<any>(`/api/v1/history/${lookId}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
      }),

    delete: (lookId: string) =>
      request<any>(`/api/v1/history/${lookId}`, {
        method: 'DELETE',
      }),
  },

  // --- User Profile ---
  profile: {
    get: () => request<any>('/api/v1/profile'),

    update: (updates: { name?: string; profile_photo?: string }) =>
      request<any>('/api/v1/profile', {
        method: 'PUT',
        body: JSON.stringify(updates),
      }),
  },

  // --- Admin Catalogue Management ---
  admin: {
    createItem: (item: any) =>
      request<any>('/api/v1/admin/catalogue', {
        method: 'POST',
        body: JSON.stringify(item),
      }),

    updateItem: (itemId: string, update: any) =>
      request<any>(`/api/v1/admin/catalogue/${itemId}`, {
        method: 'PUT',
        body: JSON.stringify(update),
      }),

    deleteItem: (itemId: string) =>
      request<any>(`/api/v1/admin/catalogue/${itemId}`, {
        method: 'DELETE',
      }),
  },
};
