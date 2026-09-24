"use client";

import { useRef, useState, type FocusEvent, type PointerEvent } from "react";
import type { Scene } from "@/lib/queries";
import { Tooltip, TipRow, TipTitle } from "./shared";
import { fixed } from "@/lib/format";

/**
 * City x genre lift, with the evidence printed beside every bar.
 * A lift of 20 backed by three records has to *look* weaker than a lift of 16
 * backed by eleven - so bars under the evidence floor are drawn in the
 * de-emphasis grey and marked "thin" in text (never colour alone).
 */
export default function LiftBars({ scenes, strongMin = 5 }: { scenes: Scene[]; strongMin?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<{ s: Scene; x: number; y: number; w: number } | null>(null);
  const max = Math.max(...scenes.map((s) => s.lift)) * 1.12;

  const show = (s: Scene, clientX: number, clientY: number) => {
    const r = box.current!.getBoundingClientRect();
    setTip({ s, x: clientX - r.left, y: clientY - r.top, w: r.width });
  };
  const onMove = (s: Scene) => (e: PointerEvent) => show(s, e.clientX, e.clientY);
  const onFocus = (s: Scene) => (e: FocusEvent<HTMLElement>) => {
    const t = e.currentTarget.getBoundingClientRect();
    show(s, t.left + t.width * 0.55, t.top + t.height / 2);
  };

  return (
    <div ref={box} className="relative">
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm bg-series" /> {strongMin}+ features behind it
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-4 rounded-sm bg-deemph" /> fewer than {strongMin} (thin evidence)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-px bg-muted" /> 1× = archive average
        </span>
      </div>

      <ul className="space-y-1">
        {scenes.map((s) => {
          const strong = s.features >= strongMin;
          const key = `${s.city}-${s.state}-${s.genre}`;
          return (
            <li
              key={key}
              tabIndex={0}
              onPointerMove={onMove(s)}
              onPointerLeave={() => setTip(null)}
              onFocus={onFocus(s)}
              onBlur={() => setTip(null)}
              aria-label={`${s.city}, ${s.genre}: lift ${fixed(s.lift, 1)}, ${s.features} of ${s.cityFeatures} features`}
              className="grid grid-cols-[1fr_auto] items-center gap-x-3 rounded-md px-2 py-1.5 outline-offset-0 hover:bg-surface-2 sm:grid-cols-[11rem_1fr_6.5rem]"
            >
              <div className="col-span-2 truncate text-sm sm:col-span-1">
                <span className="text-ink">{s.city}</span>
                <span className="text-muted"> · </span>
                <span className="text-ink-2">{s.genre}</span>
              </div>
              <div className="relative h-5">
                <div
                  className="absolute inset-y-0 w-px bg-muted/60"
                  style={{ left: `${(1 / max) * 100}%` }}
                  aria-hidden="true"
                />
                <div
                  className={`absolute left-0 top-1/2 h-3.5 -translate-y-1/2 rounded-r-[4px] ${strong ? "bg-series" : "bg-deemph"}`}
                  style={{ width: `${(s.lift / max) * 100}%` }}
                />
                <span
                  className="absolute top-1/2 -translate-y-1/2 pl-1.5 text-xs font-semibold text-ink tnum"
                  style={{ left: `${(s.lift / max) * 100}%` }}
                >
                  {fixed(s.lift, 1)}×
                </span>
              </div>
              <div className="text-right text-xs text-ink-2 tnum">
                {s.features} of {s.cityFeatures}
                {!strong && <span className="text-muted"> · thin</span>}
              </div>
            </li>
          );
        })}
      </ul>

      {tip && (
        <Tooltip x={tip.x} y={tip.y} containerWidth={tip.w}>
          <TipTitle>
            {tip.s.city}
            {tip.s.state ? `, ${tip.s.state}` : `, ${tip.s.country}`} · {tip.s.genre}
          </TipTitle>
          <TipRow value={`${fixed(tip.s.lift, 1)}×`} label="lift" keyColor={tip.s.features >= strongMin ? "var(--series)" : "var(--deemph)"} />
          <div className="mt-1 space-y-0.5 text-ink-2">
            <div>
              <span className="text-ink tnum">{fixed(tip.s.cityShare * 100, 0)}%</span> of {tip.s.city}&apos;s features
              ({tip.s.features}/{tip.s.cityFeatures})
            </div>
            <div>
              vs <span className="text-ink tnum">{fixed(tip.s.globalShare * 100, 1)}%</span> of the whole archive
            </div>
          </div>
        </Tooltip>
      )}
    </div>
  );
}
