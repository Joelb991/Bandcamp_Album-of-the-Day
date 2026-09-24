import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowIcon, ExternalIcon } from "./icons";

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-6xl px-4 sm:px-6 ${className}`}>{children}</div>;
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent">{children}</p>;
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <Container className="pb-8 pt-12 sm:pt-16">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{title}</h1>
      {children && <div className="mt-4 max-w-2xl text-base leading-relaxed text-ink-2">{children}</div>}
    </Container>
  );
}

/** Stat tile: label, value (proportional figures), optional note. */
export function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3.5">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tracking-tight text-ink">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-surface p-4 sm:p-6 ${className}`}>{children}</div>;
}

export function ChartTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
    </div>
  );
}

export function Caveat({ children }: { children: ReactNode }) {
  return (
    <div className="mt-5 border-l-2 border-baseline pl-4 text-sm leading-relaxed text-muted">
      <span className="font-medium text-ink-2">Caveat. </span>
      {children}
    </div>
  );
}

export function ButtonLink({
  href,
  children,
  primary = false,
  external = false,
}: {
  href: string;
  children: ReactNode;
  primary?: boolean;
  external?: boolean;
}) {
  const cls = `inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
    primary
      ? "bg-ink text-bg hover:bg-white"
      : "border border-line text-ink-2 hover:border-baseline hover:bg-surface-2 hover:text-ink"
  }`;
  if (external) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className={cls}>
        {children} <ExternalIcon className="h-3.5 w-3.5" />
      </a>
    );
  }
  return (
    <Link href={href} className={cls}>
      {children} <ArrowIcon className="h-3.5 w-3.5" />
    </Link>
  );
}
