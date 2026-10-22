/**
 * StyleVision — Shared Type Definitions
 */

export type TryOnCategory = 'outfit' | 'accessories' | 'makeup' | 'hairstyle' | 'complete';

export interface StyleItem {
  id: string;
  name: string;
  category: TryOnCategory;
  subcategory?: string;
  thumbnail: string;
  description?: string;
  tags?: string[];
  color?: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  savedLooksCount: number;
  wardrobeCount?: number;
  is_admin?: boolean;
  createdAt: string;
}

export interface SavedLook {
  id: string;
  title: string;
  category: TryOnCategory;
  originalImage: string;
  resultImage: string;
  createdAt: string;
  styleItemName: string;
}

export interface WardrobeItem {
  outfit_id: string;
  user_id: string;
  name: string;
  category: string;
  outfit_image: string;
  color?: string;
  notes?: string;
  uploaded_at: string;
}
