/**
 * StyleVision — Shared Type Definitions
 */

export type TryOnCategory = 'outfit' | 'accessories' | 'makeup' | 'hairstyle';

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
