/**
 * StyleVision — Design System & Theme
 * "L'Atelier Haute Couture" — Prestige Obsidian, Champagne Gold & Emerald Luxe.
 * Transforms the visual identity into an ultra-high-end fashion editorial experience.
 */

export const Colors = {
  // Haute Couture Gold & Amber Accents
  primary: '#E5A93C',           // Rich Champagne Gold
  primaryLight: '#F6CF7A',      // Luminous Warm Gold
  primaryDark: '#B88222',       // Deep Burnished Bronze
  primaryGlow: 'rgba(229, 169, 60, 0.25)', // Golden ambient radiance
  accentPink: '#FF3366',        // Rose Petal / Haute Pink
  accentGold: '#FFD700',        // Pure 24K Gold
  accentEmerald: '#10B981',     // Fine Jewelry Emerald
  accentCyan: '#06B6D4',        // Electric Lapis Lazuli

  // Obsidian & Titanium Background Hierarchy
  background: '#07080B',         // Deep Obsidian Black
  backgroundSecondary: '#0E121A',// Midnight Slate
  surface: '#141A24',            // Brushed Titanium
  surfaceHover: '#1E2636',       // Interactive Slate
  surfaceCard: '#111621',        // Haute Couture Matte Obsidian Card

  // Text Hierarchy
  textPrimary: '#FFFFFF',        // Pristine Diamond White
  textSecondary: '#E2E8F0',      // Platinum Silk
  textMuted: '#8392A5',          // Cool Granite Slate
  textInverse: '#07080B',        // Deep Obsidian Black

  // Luxury Metallic Borders & Separators
  border: '#242D3D',            // Refined Slate Platinum
  borderLight: '#344056',       // Brightened Border
  borderFocus: '#E5A93C',       // Luminous Gold Ring

  // Semantic Status Colors
  success: '#10B981',
  successBg: 'rgba(16, 185, 129, 0.15)',
  warning: '#F59E0B',
  warningBg: 'rgba(245, 158, 11, 0.15)',
  error: '#EF4444',
  errorBg: 'rgba(239, 68, 68, 0.15)',
  info: '#06B6D4',
  infoBg: 'rgba(6, 182, 212, 0.15)',

  // Overlays
  overlay: 'rgba(7, 8, 11, 0.85)',
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const BorderRadius = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
  full: 9999,
};

export const Typography = {
  sizes: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 17,
    xl: 21,
    xxl: 28,
    hero: 36,
  },
  weights: {
    regular: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
    heavy: '800' as const,
  },
};

export const Shadows = {
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.50,
    shadowRadius: 10,
    elevation: 8,
  },
  glow: {
    shadowColor: '#E5A93C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.40,
    shadowRadius: 14,
    elevation: 10,
  },
};
