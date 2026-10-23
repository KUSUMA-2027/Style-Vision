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
  slot?: string | null;
  closeupResultUrl?: string | null;
  closeupOriginalUrl?: string | null;
  appliedAt: number;
}

export interface SessionItem {
  imageId: string;
  tryonId: string;
  stage: Stage;
  slot: string | null;
  title: string;
  url: string;
  mode?: string;
}

interface StylingSessionValue {
  ready: boolean;
  base: PortraitRef | null;
  current: PortraitRef | null;
  stages: Partial<Record<Stage, StageResult>>;
  items: SessionItem[];
  selections: Partial<Record<Stage, any>>;
  nextStage: Stage | null;
  ensureSession: (portrait: PortraitRef) => void;
  startSession: (base: PortraitRef) => void;
  setSelection: (stage: Stage, selection: any) => void;
  applyStageResult: (result: StageResult) => void;
  syncSession: () => Promise<void>;
  removeItem: (item: SessionItem) => Promise<boolean>;
  resetSession: () => void;
  undoEverything: () => Promise<void>;
  restoreFromServer: () => Promise<void>;
}

const StylingSessionContext = createContext<StylingSessionValue | null>(null);

export function StylingSessionProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [base, setBase] = useState<PortraitRef | null>(null);
  const [current, setCurrent] = useState<PortraitRef | null>(null);
  const [stages, setStages] = useState<Partial<Record<Stage, StageResult>>>({});
  const [items, setItems] = useState<SessionItem[]>([]);
  const [selections, setSelections] = useState<Partial<Record<Stage, any>>>({});

  const mapServerItem = (it: any): SessionItem | null => {
    if (!it?.image_id || !it?.stage) return null;
    return {
      imageId: it.image_id,
      tryonId: it.tryon_id ?? '',
      stage: it.stage,
      slot: it.slot ?? null,
      title: it.title ?? it.stage,
      url: it.url ?? '',
      mode: it.mode ?? (it.stage === 'outfit' ? 'catvton' : undefined),
    };
  };

  /** Rebuild local session state (current image + items + stages) from the server. */
  const applyServerSession = useCallback((data: any) => {
    if (data?.current_image?.url && data?.current_image?.image_id) {
      setCurrent({ image_id: data.current_image.image_id, url: data.current_image.url });
    }
    const serverItems: SessionItem[] = (data?.items ?? [])
      .map(mapServerItem)
      .filter(Boolean) as SessionItem[];
    setItems(serverItems);

    const builtStages: Partial<Record<Stage, StageResult>> = {};
    for (const it of serverItems) {
      builtStages[it.stage] = {
        stage: it.stage,
        tryonId: it.tryonId,
        resultImageId: it.imageId,
        resultUrl: it.url,
        sourceUrl: '',
        title: it.title,
        slot: it.slot,
        mode: it.mode ?? (it.stage === 'outfit' ? 'catvton' : undefined),
        appliedAt: Date.now(),
      };
    }
    if (data?.stages) {
      for (const [stg, info] of Object.entries(data.stages)) {
        if (info && builtStages[stg as Stage]) {
          const m = (info as any).mode || (info as any).metadata?.mode;
          if (m) builtStages[stg as Stage]!.mode = m;
        }
      }
    }
    setStages(builtStages);
  }, []);

  /** Fetch the authoritative session state from the backend. */
  const syncSession = useCallback(async () => {
    if (!base?.image_id) return;
    try {
      const res = await api.tryon.getSessionStages(base.image_id);
      applyServerSession(res);
    } catch {
      // Offline or expired token — keep local state
    }
  }, [base, applyServerSession]);

  /**
   * Restore an in-progress styling session from the server:
   * latest portrait → current image + live items rooted at that portrait.
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
      try {
        const res = await api.tryon.getSessionStages(latest.image_id);
        applyServerSession(res);
        // No applied items yet → current stays at the base portrait
        if (!res?.current_image) setCurrent(restoredBase);
      } catch {
        setCurrent(restoredBase);
      }
    } catch {
      // Not authenticated yet or offline — start with an empty session
    } finally {
      setReady(true);
    }
  }, [applyServerSession]);

  useEffect(() => {
    restoreFromServer();
  }, [restoreFromServer]);

  /** Begin a NEW styling session from a fresh portrait upload. */
  const startSession = useCallback((portrait: PortraitRef) => {
    setBase(portrait);
    setCurrent(portrait);
    setStages({});
    setItems([]);
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
   * Record a completed stage result. Optimistically set the result as the
   * new "current" image, then reconcile with the authoritative server state
   * (the backend already handles replacement + replay of preserved items).
   * No forced stage clearing — the user may style stages in ANY order.
   */
  const applyStageResult = useCallback((result: StageResult) => {
    setStages((prev) => ({ ...prev, [result.stage]: result }));
    const resultImageId = result.resultImageId || result.tryonId;
    if (resultImageId) {
      setCurrent({ image_id: resultImageId, url: result.resultUrl });
    }
    setItems((prev) => [
      ...prev.filter((it) => {
        // Single-item stages: outfit and hairstyle are singular
        if (result.stage === 'outfit' || result.stage === 'hairstyle') {
          return it.stage !== result.stage;
        }
        // Slotted stages: replace only if the slot matches
        if (it.stage === result.stage && result.slot && it.slot === result.slot) {
          return false;
        }
        return true;
      }),
      {
        imageId: resultImageId,
        tryonId: result.tryonId,
        stage: result.stage,
        slot: result.slot ?? null,
        title: result.title,
        url: result.resultUrl,
        mode: result.mode ?? (result.stage === 'outfit' ? 'catvton' : undefined),
      },
    ]);
    void syncSession();
  }, [syncSession]);

  /**
   * Remove an applied item from the look. The backend strips it from the
   * chain, rebuilds the image, and replays the preserved items; the session
   * then syncs to the rebuilt state.
   */
  const removeItem = useCallback(
    async (item: SessionItem): Promise<boolean> => {
      if (!current?.image_id) return false;
      try {
        const res = await api.tryon.removeItem(current.image_id, item.stage, item.slot ?? undefined);
        if (res?.status === 'failed') {
          return false;
        }
        await syncSession();
        return true;
      } catch (err: any) {
        throw new Error(err?.message || 'Could not remove this item.');
      }
    },
    [current, syncSession]
  );

  /**
   * Undo everything: completely deletes the active uploaded model portrait
   * and all styling stages on both server and client so the user starts 100% fresh.
   */
  const undoEverything = useCallback(async () => {
    try {
      await api.upload.resetPortrait();
    } catch {
      // Offline / network failure — continue with local wipe
    }
    setBase(null);
    setCurrent(null);
    setStages({});
    setItems([]);
    setSelections({});
  }, []);

  const resetSession = useCallback(() => {
    setBase(null);
    setCurrent(null);
    setStages({});
    setItems([]);
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
      items,
      selections,
      nextStage,
      ensureSession,
      startSession,
      setSelection,
      applyStageResult,
      syncSession,
      removeItem,
      resetSession,
      undoEverything,
      restoreFromServer,
    }),
    [
      ready,
      base,
      current,
      stages,
      items,
      selections,
      nextStage,
      ensureSession,
      startSession,
      setSelection,
      applyStageResult,
      syncSession,
      removeItem,
      resetSession,
      undoEverything,
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
