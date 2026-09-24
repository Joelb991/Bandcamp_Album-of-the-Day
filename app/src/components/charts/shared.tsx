"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Measures a container so charts render at true pixel width (text stays
 * 11-12px on a phone instead of shrinking with a viewBox). Until the first
 * measurement the chart renders at `fallback` and scales to fit.
 */
export function useWidth<T extends HTMLElement>(fallback = 720) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width || fallback, width > 0] as const;
}

export const linear =
  (d0: number, d1: number, r0: number, r1: number) =>
  (v: number) =>
    r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);

/** Floating readout. Values lead (strong), labels follow (muted). */
export function Tooltip({
  x,
  y,
  containerWidth,
  children,
}: {
  x: number;
  y: number;
  containerWidth: number;
  children: ReactNode;
}) {
  const flip = x > containerWidth - 200;
  return (
    <div
      role="status"
      className="pointer-events-none absolute z-20 min-w-36 rounded-lg border border-line bg-surface-3/95 px-3 py-2 text-xs shadow-xl shadow-black/40 backdrop-blur"
      style={{
        left: flip ? undefined : x + 14,
        right: flip ? containerWidth - x + 14 : undefined,
        top: Math.max(0, y - 12),
      }}
    >
      {children}
    </div>
  );
}

export function TipTitle({ children }: { children: ReactNode }) {
  return <div className="mb-1 text-[11px] text-muted">{children}</div>;
}

export function TipRow({ value, label, keyColor }: { value: ReactNode; label?: ReactNode; keyColor?: string }) {
  return (
    <div className="flex items-baseline gap-2 whitespace-nowrap">
      {keyColor && <span className="inline-block h-0.5 w-3 translate-y-[-3px] rounded" style={{ background: keyColor }} />}
      <span className="text-sm font-semibold text-ink tnum">{value}</span>
      {label && <span className="text-ink-2">{label}</span>}
    </div>
  );
}
