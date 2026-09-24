"use client";

import { useState, type KeyboardEvent, type PointerEvent } from "react";
import type { Writer } from "@/lib/queries";
import { linear, Tooltip, TipRow, TipTitle, useWidth } from "./shared";

/**
 * Reviews (x) against genre entropy (y). Specialists sit low, generalists
 * high. Hover snaps to the nearest writer so nobody has to land on an 8px dot.
 */
export default function WriterScatter({ writers, labelNames }: { writers: Writer[]; labelNames: string[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const height = 320;
  const m = { top: 20, right: 20, bottom: 44, left: 44 };

  const xMax = Math.ceil(Math.max(...writers.map((w) => w.reviews)) / 20) * 20;
  const x = linear(10, xMax, m.left, width - m.right);
  const y = linear(0, 3.6, height - m.bottom, m.top);
  const xTicks = Array.from({ length: xMax / 20 }, (_, i) => (i + 1) * 20);
  const yTicks = [0, 1, 2, 3];

  const nearest = (px: number, py: number) => {
    let best = -1;
    let bestD = 44 ** 2;
    writers.forEach((w, i) => {
      const d = (x(w.reviews) - px) ** 2 + (y(w.entropy) - py) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    return best < 0 ? null : best;
  };

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const k = width / box.width;
    setActive(nearest((e.clientX - box.left) * k, (e.clientY - box.top) * k));
  };

  // Keyboard: arrows step through writers in order of volume.
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") setActive((a) => Math.min(writers.length - 1, (a ?? -1) + 1));
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") setActive((a) => Math.max(0, (a ?? 1) - 1));
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  };

  const a = active !== null ? writers[active] : null;

  return (
    <div ref={ref} className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="block h-auto w-full touch-pan-y"
        role="img"
        aria-label="Scatter plot of Bandcamp Daily writers: reviews written against the spread of genres they cover."
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={() => setActive((v) => v ?? 0)}
        onBlur={() => setActive(null)}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--baseline)" : "var(--line)"} />
            <text x={m.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px] tnum">
              {t}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={height - m.bottom + 18} textAnchor="middle" className="fill-muted text-[11px] tnum">
            {t}
          </text>
        ))}
        <text x={width - m.right} y={height - 6} textAnchor="end" className="fill-muted text-[11px]">
          Reviews written →
        </text>
        <text x={m.left} y={m.top - 8} className="fill-muted text-[11px]">
          Genre spread (bits) ↑ broader
        </text>

        {writers.map((w, i) => (
          <circle
            key={w.author}
            cx={x(w.reviews)}
            cy={y(w.entropy)}
            r={active === i ? 6 : 4}
            fill="var(--series)"
            fillOpacity={active === null || active === i ? 1 : 0.55}
            stroke="var(--surface)"
            strokeWidth={2}
          />
        ))}

        {writers
          .filter((w) => labelNames.includes(w.author))
          .map((w) => {
            const right = x(w.reviews) < width * 0.7;
            return (
              <text
                key={w.author}
                x={x(w.reviews) + (right ? 10 : -10)}
                y={y(w.entropy)}
                dy="0.32em"
                textAnchor={right ? "start" : "end"}
                className="pointer-events-none fill-ink-2 text-[12px]"
              >
                {w.author}
              </text>
            );
          })}

        <rect
          x={0}
          y={0}
          width={width}
          height={height}
          fill="transparent"
          onPointerMove={onMove}
          onPointerDown={onMove}
          onPointerLeave={() => setActive(null)}
        />
      </svg>

      {a && (
        <Tooltip x={x(a.reviews)} y={y(a.entropy)} containerWidth={width}>
          <TipTitle>{a.author}</TipTitle>
          <TipRow value={a.entropy.toFixed(2)} label="bits of genre spread" keyColor="var(--series)" />
          <div className="mt-1 space-y-0.5 text-ink-2">
            <div>
              <span className="text-ink tnum">{a.reviews}</span> reviews · <span className="text-ink tnum">{a.genres}</span> genres ·{" "}
              <span className="text-ink tnum">{a.countries}</span> countries
            </div>
            <div>
              <span className="text-ink tnum">{a.indieShare.toFixed(0)}%</span> self-released
            </div>
          </div>
        </Tooltip>
      )}
    </div>
  );
}
