import { ImageResponse } from "next/og";
import { getHeadline } from "@/lib/queries";
import { fmtInt, fixed } from "@/lib/format";

export const alt = "AOTD Analytics: fifteen years of Bandcamp's Album of the Day, in aggregate";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 86400;

/** The link preview for LinkedIn, Slack and email: the question plus four numbers. */
export default async function OpengraphImage() {
  const h = await getHeadline();
  const stats = [
    [fmtInt(h.features), "features"],
    [String(h.countries), "countries"],
    [`${fixed(h.usShare, 0)}%`, "from US labels"],
    [`${fixed(h.indieShare, 0)}%`, "self-released"],
  ];
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0f1215",
          color: "#f2f4f3",
          padding: "72px 80px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 28, color: "#7fcadd", letterSpacing: 2 }}>
          <div style={{ width: 28, height: 28, borderRadius: 14, border: "4px solid #2fa2bc" }} />
          AOTD ANALYTICS
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ fontSize: 76, fontWeight: 700, lineHeight: 1.05, letterSpacing: -2 }}>Where does editorial attention actually go?</div>
          <div style={{ fontSize: 30, color: "#b9c0c2" }}>
            {`Fifteen years of Bandcamp Daily's Album of the Day, ${h.firstDate.slice(0, 4)}–${h.lastDate.slice(0, 4)}`}
          </div>
        </div>
        <div style={{ display: "flex", gap: 56 }}>
          {stats.map(([v, l]) => (
            <div key={l} style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 52, fontWeight: 700, color: "#f2f4f3" }}>{v}</div>
              <div style={{ fontSize: 24, color: "#858e92" }}>{l}</div>
            </div>
          ))}
        </div>
      </div>
    ),
    size,
  );
}
