/**
 * StyleVision — Styling Session Context
 *
 * Implements the client's critical "continuous styling workflow" requirement:
 * each stage (Outfit → Accessories → Makeup → Hairstyle → Complete Look) starts
 * from the LATEST generated image of the previous stage instead of repeatedly
 * from the original photo. The backend registers every stage result in the
 * unified image registry; this context tracks the chain client-side and can
 * restore it from the server after an app restart.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { api } from './api';

export const STAGE_ORDER = ['outfit', 'accessories', 'makeup', 'hairstyle'] as const;
export type Stage = (typeof STAGE_ORDER)[number];

export const NEXT_STAGE_ROUTE: Record<Stage, string> = {
  outfit: '/try-on/accessories',
  accessories: '/try-on/makeup',
  makeup: '/try-on/hairstyle',
  hairstyle: '/complete-look',
};

export const STAGE_LABEL: Record<Stage, string> = {
  outfit: 'Outfit',
  accessories: 'Accessories',
  makeup: 'Makeup',
  hairstyle: 'Hairstyle',
};

export const STAGE_ROUTE: Record<Stage, string> = {
  outfit: '/try-on/outfit',
  accessories: '/try-on/accessories',
  makeup: '/try-on/makeup',
  hairstyle: '/try-on/hairstyle',
};

export interface PortraitRef {
  image_id: string;
  url: string;
}

export interface StageResult {
  stage: Stage;
  tryonId: string;
  resultImageId: string | null;
  resultUrl: string;
  sourceUrl: string;
  title: string;
  style?: string;
  mode?: string;
  closeupResultUrl?: string | null;
  closeupOriginalUrl?: string | null;
  appliedAt: number;
}

interface StylingSessionValue {
  ready: boolean;
  base: PortraitRef | null;
  current: PortraitRef | null;
  stages: Partial<Record<Stage, StageResult>>;
  selections: Partial<Record<Stage, any>>;
  nextStage: Stage | null;
  ensureSession: (portrait: PortraitRef) => void;
  startSession: (base: PortraitRef) => void;
  setSelection: (stage: Stage, selection: any) => void;
  applyStageResult: (result: StageResult) => void;
  resetSession: () => void;
  restoreFromServer: () => Promise<void>;
}

const StylingSessionContext = createContext<StylingSessionValue | null>(null);

export function StylingSessionProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [base, setBase] = useState<PortraitRef | null>(null);
  const [current, setCurrent] = useState<PortraitRef | null>(null);
  const [stages, setStages] = useState<Partial<Record<Stage, StageResult>>>({});
  const [selections, setSelections] = useState<Partial<Record<Stage, any>>>({});

  /**
   * Restore an in-progress styling session from the server:
   * latest portrait → per-stage results rooted at that portrait.
   */
  const restoreFromServer = useCallback(async () => {
    try {
      const latest = await api.upload.getLatest();
      if (!latest?.image_id) {
        setReady(true);
        return;
      }
      const restoredBase: PortraitRef = { image_id: latest.image_id, url: latest.url };
      setBase(restoredBase);

      let restoredCurrent: PortraitRef = restoredBase;
      const restoredStages: Partial<Record<Stage, StageResult>> = {};
      try {
        const res = await api.tryon.getSessionStages(latest.image_id);
        for (const stage of STAGE_ORDER) {
          const s = res?.stages?.[stage];
          if (s?.url && s?.image_id) {
            restoredStages[stage] = {
              stage,
              tryonId: s.tryon_id ?? '',
              resultImageId: s.image_id,
              resultUrl: s.url,
              sourceUrl: s.metadata?.parent_url ?? restoredBase.url,
              title: s.metadata?.style_name ?? s.metadata?.garment_name ?? STAGE_LABEL[stage],
              mode: s.metadata?.mode,
              appliedAt: s.created_at ? new Date(s.created_at).getTime() : Date.now(),
            };
          }
        }
        // The true current image is the server's latest stage result overall
        // (critical when items were re-applied / replaced out of order)
        if (res?.current_image?.url && res?.current_image?.image_id) {
          restoredCurrent = { image_id: res.current_image.image_id, url: res.current_image.url };
        } else {
          // Fallback: deepest applied stage in pipeline order
          for (const stage of STAGE_ORDER) {
            const s = restoredStages[stage];
            if (s) restoredCurrent = { image_id: s.resultImageId || s.tryonId, url: s.resultUrl };
          }
        }
      } catch {
        // Session stages endpoint unavailable — base portrait still restored
      }
      setStages(restoredStages);
      setCurrent(restoredCurrent);
    } catch {
      // Not authenticated yet or offline — start with an empty session
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    restoreFromServer();
  }, [restoreFromServer]);

  /** Begin a NEW styling session from a fresh portrait upload. */
  const startSession = useCallback((portrait: PortraitRef) => {
    setBase(portrait);
    setCurrent(portrait);
    setStages({});
    setSelections({});
  }, []);

  /** If no session exists yet, adopt this portrait as the session base. */
  const ensureSession = useCallback(
    (portrait: PortraitRef) => {
      if (!base) {
        setBase(portrait);
        setCurrent((prevCurrent) => prevCurrent ?? portrait);
      }
    },
    [base]
  );

  const setSelection = useCallback((stage: Stage, selection: any) => {
    setSelections((prev) => ({ ...prev, [stage]: selection }));
  }, []);

  /**
   * Record a completed stage result. The result becomes the new "current"
   * image that subsequent stages chain from. Re-running an earlier stage
   * invalidates later results (they were generated from the previous chain)
   * while retaining the user's selections for one-tap re-apply.
   */
  const applyStageResult = useCallback((result: StageResult) => {
    setStages((prev) => {
      const idx = STAGE_ORDER.indexOf(result.stage);
      const next: Partial<Record<Stage, StageResult>> = { ...prev };
      for (const later of STAGE_ORDER.slice(idx + 1)) {
        delete next[later];
      }
      next[result.stage] = result;
      return next;
    });
    const resultImageId = result.resultImageId || result.tryonId;
    if (resultImageId) {
      setCurrent({ image_id: resultImageId, url: result.resultUrl });
    }
  }, []);

  const resetSession = useCallback(() => {
    setBase(null);
    setCurrent(null);
    setStages({});
    setSelections({});
  }, []);

  const nextStage = useMemo<Stage | null>(() => {
    for (const stage of STAGE_ORDER) {
      if (!stages[stage]) return stage;
    }
    return null;
  }, [stages]);

  const value = useMemo<StylingSessionValue>(
    () => ({
      ready,
      base,
      current,
      stages,
      selections,
      nextStage,
      ensureSession,
      startSession,
      setSelection,
      applyStageResult,
      resetSession,
      restoreFromServer,
    }),
    [
      ready,
      base,
      current,
      stages,
      selections,
      nextStage,
      ensureSession,
      startSession,
      setSelection,
      applyStageResult,
      resetSession,
      restoreFromServer,
    ]
  );

  return <StylingSessionContext.Provider value={value}>{children}</StylingSessionContext.Provider>;
}

export function useStylingSession(): StylingSessionValue {
  const ctx = useContext(StylingSessionContext);
  if (!ctx) {
    throw new Error('useStylingSession must be used within a StylingSessionProvider');
  }
  return ctx;
}
