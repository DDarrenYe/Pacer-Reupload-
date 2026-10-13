import { useId } from "react";

import type { RankName } from "../ranks";

interface Palette {
  light: string;
  dark: string;
  ribbon: string;
}

const PALETTES: Record<RankName, Palette> = {
  Bronze: { light: "#f0b47c", dark: "#8a4b20", ribbon: "#a3582a" },
  Silver: { light: "#f4f6f8", dark: "#7f8a95", ribbon: "#5f6b78" },
  Gold: { light: "#ffe58f", dark: "#b07d05", ribbon: "#c0392b" },
  Platinum: { light: "#d9f7f3", dark: "#2f8f88", ribbon: "#1f6f6a" },
  Diamond: { light: "#d8ecff", dark: "#2f62d0", ribbon: "#24479c" },
  "Pace Setter": { light: "#ffc2a8", dark: "#c0321a", ribbon: "#f08c00" },
  Apex: { light: "#ecd5ff", dark: "#6a2fd0", ribbon: "#f2b705" },
};

const RIM = "rgba(0,0,0,0.35)";
const EMBLEM = "#ffffff";

/** A medal for each rank. Every rank has its own shape and emblem as well as colour,
 * so they stay distinct in greyscale and for colour-blind runners. */
export default function RankMedal({ rank, size = 48 }: { rank: RankName; size?: number }) {
  const id = useId().replace(/:/g, "");
  const p = PALETTES[rank];
  const fill = `url(#${id}-face)`;
  return (
    <svg width={size} height={size * 1.25} viewBox="0 0 64 80" role="img" aria-label={`${rank} rank`}>
      <defs>
        <linearGradient id={`${id}-face`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={p.light} />
          <stop offset="1" stopColor={p.dark} />
        </linearGradient>
      </defs>
      {/* Ribbon */}
      <path d="M18 2 L30 2 L36 26 L26 30 Z" fill={p.ribbon} />
      <path d="M46 2 L34 2 L28 26 L38 30 Z" fill={p.ribbon} opacity="0.85" />
      <Face rank={rank} fill={fill} />
      <Emblem rank={rank} stroke={p.dark} />
    </svg>
  );
}

function Face({ rank, fill }: { rank: RankName; fill: string }) {
  switch (rank) {
    case "Platinum":
      return <path d="M32 26 L51 37 L51 59 L32 70 L13 59 L13 37 Z" fill={fill} stroke={RIM} strokeWidth="1.5" />;
    case "Diamond":
      return (
        <g stroke={RIM} strokeWidth="1.5" strokeLinejoin="round">
          <path d="M20 30 L44 30 L54 42 L32 74 L10 42 Z" fill={fill} />
          <path d="M10 42 L54 42 M20 30 L26 42 L32 30 L38 42 L44 30 M26 42 L32 74 L38 42" fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth="1.2" />
        </g>
      );
    case "Pace Setter":
      return <path d="M32 26 L52 32 L52 50 C52 62 43 70 32 75 C21 70 12 62 12 50 L12 32 Z" fill={fill} stroke={RIM} strokeWidth="1.5" />;
    case "Apex":
      return (
        <g>
          <circle cx="32" cy="52" r="20" fill={fill} stroke={RIM} strokeWidth="1.5" />
          {/* Crown */}
          <path d="M18 34 L22 22 L27 30 L32 18 L37 30 L42 22 L46 34 Z" fill="#f5c542" stroke="#9a6b00" strokeWidth="1.2" strokeLinejoin="round" />
        </g>
      );
    default:
      return <circle cx="32" cy="50" r="21" fill={fill} stroke={RIM} strokeWidth="1.5" />;
  }
}

function Emblem({ rank, stroke }: { rank: RankName; stroke: string }) {
  const common = { fill: EMBLEM, stroke, strokeWidth: 1.2, strokeLinejoin: "round" as const };
  const chevron = (y: number) => <path key={y} d={`M22 ${y + 6} L32 ${y} L42 ${y + 6} L42 ${y + 10} L32 ${y + 4} L22 ${y + 10} Z`} {...common} />;
  switch (rank) {
    case "Bronze":
      return chevron(45);
    case "Silver":
      return <>{[40, 50].map(chevron)}</>;
    case "Gold":
      return <>{[36, 45, 54].map(chevron)}</>;
    case "Platinum":
      return <path d="M32 37 L35.5 45 L44 45.6 L37.5 51 L39.6 59.5 L32 55 L24.4 59.5 L26.5 51 L20 45.6 L28.5 45 Z" {...common} />;
    case "Diamond":
      return <path d="M32 44 L36 49 L32 56 L28 49 Z" {...common} />;
    case "Pace Setter":
      return (
        <g>
          {/* Wings */}
          <path d="M14 44 C20 42 24 44 27 48 C22 49 18 48 14 44 Z M50 44 C44 42 40 44 37 48 C42 49 46 48 50 44 Z" {...common} />
          {/* Lightning bolt */}
          <path d="M34 34 L25 51 L31 51 L28 66 L39 46 L33 46 L37 34 Z" {...common} />
        </g>
      );
    case "Apex":
      return (
        <g>
          <path d="M19 62 L28 46 L32 52 L37 43 L45 62 Z" {...common} />
          <circle cx="40" cy="41" r="2.4" fill={EMBLEM} stroke={stroke} strokeWidth="1" />
        </g>
      );
  }
}
