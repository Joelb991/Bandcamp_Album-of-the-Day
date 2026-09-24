import type { ReactNode } from "react";

export type Column<T> = {
  label: string;
  value: (row: T) => ReactNode;
  numeric?: boolean;
};

/** The table-view twin every chart ships with, collapsed by default. */
export default function DataTable<T>({
  rows,
  columns,
  caption,
  summary = "View data as a table",
}: {
  rows: T[];
  columns: Column<T>[];
  caption: string;
  summary?: string;
}) {
  return (
    <details className="group mt-4 text-sm">
      <summary className="inline-flex cursor-pointer select-none items-center gap-1.5 text-muted hover:text-ink-2">
        <span className="inline-block transition-transform group-open:rotate-90">›</span>
        {summary}
      </summary>
      <div className="mt-3 max-h-96 overflow-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky top-0 bg-surface-2 text-xs text-muted">
            <tr>
              {columns.map((c) => (
                <th key={c.label} scope="col" className={`px-3 py-2 font-medium ${c.numeric ? "text-right" : ""}`}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-line">
                {columns.map((c) => (
                  <td key={c.label} className={`px-3 py-1.5 text-ink-2 ${c.numeric ? "text-right tnum" : ""}`}>
                    {c.value(r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
