"use client";

import { useState, type KeyboardEvent, type PointerEvent } from "react";
import { linear, Tooltip, TipRow, TipTitle, useWidth } from "./shared";
import { fixed } from "@/lib/format";

export type LinePoint = { x: number; y: number; note?: string };

type Props = {
  data: LinePoint[];
  yMax: number;
  yTicks: number[];
  /** x values that get a direct label - the story points, never all of them. */
  labelAt: number[];
  /** Marks the final point as incomplete (hollow marker, "YTD" label). */
  partialLast?: boolean;
  reference?: { y: number; label: string };
  valueLabel: string;
  ariaLabel: string;
  height?: number;
};

const fmt = (v: number) => `${fixed(v, 1)}%`;

export default function LineChart({
  data,
  yMax,
  yTicks,
  labelAt,
  partialLast,
  reference,
  valueLabel,
  ariaLabel,
  height = 260,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  // The right gutter holds the end value and the reference label ("All-time 54.8%").
  const m = { top: 28, right: reference ? 96 : 56, bottom: 28, left: 40 };
  const x = linear(data[0].x, data[data.length - 1].x, m.left, width - m.right);
  const y = linear(0, yMax, height - m.bottom, m.top);
  const path = data.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y)}`).join("");
  const everyOther = width < 520;
  const last = data.length - 1;
  // The end value sits right of its dot unless that would collide with the
  // reference label in the same gutter - then it moves to whichever side of
  // the dot is away from the reference line.
  const endBesideDot = !reference || Math.abs(y(data[last].y) - y(reference.y)) > 16;
  const endBelow = !!reference && data[last].y < reference.y;

  const nearest = (px: number) => {
    let best = 0;
    data.forEach((p, i) => {
      if (Math.abs(x(p.x) - px) < Math.abs(x(data[best].x) - px)) best = i;
    });
    return best;
  };

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    setActive(nearest(((e.clientX - box.left) / box.width) * width));
  };

  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "ArrowRight") setActive((a) => Math.min(last, (a ?? -1) + 1));
    else if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? last + 1) - 1));
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  };

  const a = active !== null ? data[active] : null;

  return (
    <div ref={ref} className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="block h-auto w-full touch-pan-y overflow-visible"
        role="img"
        aria-label={ariaLabel}
        tabIndex={0}
        onKeyDown={onKey}
        onFocus={() => setActive((a) => a ?? last)}
        onBlur={() => setActive(null)}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--baseline)" : "var(--line)"} />
            <text x={m.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px] tnum">
              {t}%
            </text>
          </g>
        ))}

        {data.map((p, i) =>
          everyOther && i % 2 && i !== last ? null : (
            <text key={p.x} x={x(p.x)} y={height - 8} textAnchor="middle" className="fill-muted text-[11px] tnum">
              {partialLast && i === last ? `${p.x}*` : p.x}
            </text>
          ),
        )}

        {reference && (
          <g>
            <line x1={m.left} x2={width - m.right} y1={y(reference.y)} y2={y(reference.y)} stroke="var(--muted)" strokeOpacity={0.55} />
            <text x={width - m.right + 6} y={y(reference.y)} dy="0.32em" className="fill-muted text-[11px]">
              {reference.label}
            </text>
          </g>
        )}

        {a && (
          <line x1={x(a.x)} x2={x(a.x)} y1={m.top - 8} y2={height - m.bottom} stroke="var(--baseline)" />
        )}

        <path d={path} fill="none" stroke="var(--series)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {data.map((p, i) => {
          const labelled = labelAt.includes(p.x);
          const isActive = active === i;
          if (!labelled && !isActive && i !== last) return null;
          const hollow = partialLast && i === last;
          return (
            <g key={p.x}>
              <circle
                cx={x(p.x)}
                cy={y(p.y)}
                r={isActive ? 5 : 4}
                fill={hollow ? "var(--surface)" : "var(--series)"}
                stroke={hollow ? "var(--series)" : "var(--surface)"}
                strokeWidth={2}
              />
              {labelled && (
                <text
                  x={i === last && endBesideDot ? x(p.x) + 9 : x(p.x)}
                  y={i === last && endBesideDot ? y(p.y) : i === last && endBelow ? y(p.y) + 20 : y(p.y) - 12}
                  dy={i === last && endBesideDot ? "0.32em" : undefined}
                  textAnchor={i === last && endBesideDot ? "start" : "middle"}
                  className="fill-ink text-[12px] font-semibold tnum"
                >
                  {fmt(p.y)}
                </text>
              )}
            </g>
          );
        })}

        <rect
          x={m.left - 10}
          y={0}
          width={width - m.left - m.right + 20}
          height={height}
          fill="transparent"
          onPointerMove={onMove}
          onPointerDown={onMove}
          onPointerLeave={() => setActive(null)}
        />
      </svg>

      {a && (
        <Tooltip x={x(a.x)} y={y(a.y)} containerWidth={width}>
          <TipTitle>
            {a.x}
            {partialLast && active === last ? " · year to date" : ""}
          </TipTitle>
          <TipRow value={fmt(a.y)} label={valueLabel} keyColor="var(--series)" />
          {a.note && <div className="mt-1 text-muted">{a.note}</div>}
        </Tooltip>
      )}
    </div>
  );
}
