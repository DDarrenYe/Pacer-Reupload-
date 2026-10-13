import { useId } from "react";

import type { RankName } from "../ranks";

/** Each rank is an army-style insignia struck in its own material, from a private's
 * single chevron to a colonel's eagle:
 *   Bronze      Private               1 chevron
 *   Silver      Private First Class   1 chevron, 1 rocker
 *   Gold        Corporal              2 chevrons
 *   Platinum    Sergeant              3 chevrons
 *   Diamond     First Sergeant        3 chevrons, 2 rockers, a diamond
 *   Emerald     Sergeant Major        3 chevrons, 3 rockers, a star
 *   Pace Setter Lieutenant Colonel    oak leaf
 *   Apex        Colonel               eagle
 * The shape changes at every rank, not just the colour, so they stay distinct in
 * greyscale and for colour-blind runners. */
interface Material {
  light: string;
  mid: string;
  dark: string;
  edge: string;
}

const MATERIALS: Record<RankName, Material> = {
  Bronze: { light: "#f3c08e", mid: "#c07a3c", dark: "#7a4116", edge: "#5a2e0e" },
  Silver: { light: "#ffffff", mid: "#c4cad1", dark: "#7c8792", edge: "#545e69" },
  Gold: { light: "#fff3b0", mid: "#e2b22c", dark: "#a2710a", edge: "#6e4c05" },
  Platinum: { light: "#f7fffd", mid: "#b9dcd8", dark: "#6f9e99", edge: "#3f6b67" },
  Diamond: { light: "#f2faff", mid: "#9ccbff", dark: "#3d7fe0", edge: "#1f4f9e" },
  Emerald: { light: "#d6ffe9", mid: "#2fbf71", dark: "#0b7a43", edge: "#05502b" },
  "Pace Setter": { light: "#ffd9a3", mid: "#f0782a", dark: "#b23a0c", edge: "#7a2306" },
  Apex: { light: "#f0dcff", mid: "#9b5cf0", dark: "#4c1d95", edge: "#2e0f63" },
};

const chevron = (y: number) => `M8 ${y + 14} L32 ${y} L56 ${y + 14} L56 ${y + 20} L32 ${y + 6} L8 ${y + 20} Z`;
const rocker = (y: number) => `M8 ${y} Q32 ${y + 10} 56 ${y} L56 ${y + 5} Q32 ${y + 15} 8 ${y + 5} Z`;

const OAK_LEAF =
  "M32 5 C36 7 38 11 37 14 C42 12 46 15 44 20 C49 20 51 25 47 28 C52 30 52 36 46 37 " +
  "C49 41 47 46 41 45 C41 49 37 52 34 50 L33.5 59 L30.5 59 L30 50 C27 52 23 49 23 45 " +
  "C17 46 15 41 18 37 C12 36 12 30 17 28 C13 25 15 20 20 20 C18 15 22 12 27 14 C26 11 28 7 32 5 Z";
const OAK_VEINS =
  "M32 11 L32 52 M32 20 L24 17 M32 20 L40 17 M32 28 L21 25 M32 28 L43 25 M32 36 L21 35 M32 36 L43 35 M32 43 L26 45 M32 43 L38 45";

const EAGLE_WING_LEFT =
  "M29 27 C23 19 13 14 2 15 L7 19 L2 21 L8 24 L3 27 L10 29 L6 32 L13 33 L10 36 L17 36 C22 35 26 33 29 31 Z";
const EAGLE_BODY = "M27 25 L37 25 L37 39 C37 45 32 49 32 49 C32 49 27 45 27 39 Z";
const EAGLE_HEAD = "M30 25 C29 19 32 15 36 16 C38 16.5 40 18 41 20 L45 21.5 L40.5 23 C39 24.5 37 25 35 25 Z";
const EAGLE_TAIL = "M28 46 L26 58 L30 55 L32 60 L34 55 L38 58 L36 46 Z";

export default function RankMedal({ rank, size = 48 }: { rank: RankName; size?: number }) {
  const id = useId().replace(/:/g, "");
  const m = MATERIALS[rank];
  const metal = { fill: `url(#${id}-metal)`, stroke: m.edge, strokeWidth: 1.4, strokeLinejoin: "round" as const };
  const engrave = { fill: "none", stroke: m.edge, strokeWidth: 1, strokeLinecap: "round" as const, opacity: 0.7 };
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={`${rank} rank`}>
      <defs>
        <linearGradient id={`${id}-metal`} x1="0" y1="0" x2="0.35" y2="1">
          <stop offset="0" stopColor={m.light} />
          <stop offset="0.45" stopColor={m.mid} />
          <stop offset="1" stopColor={m.dark} />
        </linearGradient>
      </defs>
      <Insignia rank={rank} metal={metal} engrave={engrave} light={m.light} edge={m.edge} />
    </svg>
  );
}

type Paint = Record<string, string | number>;

function Insignia({
  rank,
  metal,
  engrave,
  light,
  edge,
}: {
  rank: RankName;
  metal: Paint;
  engrave: Paint;
  light: string;
  edge: string;
}) {
  switch (rank) {
    case "Bronze":
      return <path d={chevron(21)} {...metal} />;
    case "Silver":
      return (
        <>
          <path d={chevron(13)} {...metal} />
          <path d={rocker(38)} {...metal} />
        </>
      );
    case "Gold":
      return (
        <>
          <path d={chevron(14)} {...metal} />
          <path d={chevron(25)} {...metal} />
        </>
      );
    case "Platinum":
      return (
        <>
          {[8, 18, 28].map((y) => <path key={y} d={chevron(y)} {...metal} />)}
        </>
      );
    case "Diamond":
      return (
        <>
          {[2, 10, 18].map((y) => <path key={y} d={chevron(y)} {...metal} />)}
          {[42, 50].map((y) => <path key={y} d={rocker(y)} {...metal} />)}
          {/* The first sergeant's diamond, cut like a gem */}
          <path d="M32 26 L38 33 L32 41 L26 33 Z" {...metal} />
          <path d="M26 33 L38 33 M32 26 L30 33 L32 41 M32 26 L34 33" stroke={light} strokeWidth="0.8" fill="none" opacity="0.9" />
        </>
      );
    case "Emerald":
      return (
        <>
          {[1, 8, 15].map((y) => <path key={y} d={chevron(y)} {...metal} />)}
          {[36, 42, 48].map((y) => <path key={y} d={rocker(y)} {...metal} />)}
          {/* The sergeant major's star */}
          <path d="M32 23.5 L33.9 28.2 L38.8 28.5 L35 31.6 L36.2 36.4 L32 33.7 L27.8 36.4 L29 31.6 L25.2 28.5 L30.1 28.2 Z" {...metal} />
        </>
      );
    case "Pace Setter":
      return (
        <>
          <path d={OAK_LEAF} {...metal} />
          <path d={OAK_VEINS} {...engrave} />
        </>
      );
    case "Apex":
      return (
        <>
          <path d={EAGLE_WING_LEFT} {...metal} />
          <path d={EAGLE_WING_LEFT} transform="translate(64 0) scale(-1 1)" {...metal} />
          <path d={EAGLE_TAIL} {...metal} />
          <path d={EAGLE_BODY} {...metal} />
          {/* Shield on the breast */}
          <path d="M29 28 L35 28 L35 37 C35 40 32 43 32 43 C32 43 29 40 29 37 Z" fill={light} opacity="0.55" stroke={edge} strokeWidth="0.8" />
          <path d="M30.5 31 L30.5 40 M32 31 L32 42 M33.5 31 L33.5 40" {...engrave} />
          <path d={EAGLE_HEAD} {...metal} />
          <circle cx="37" cy="19.5" r="1" fill={edge} />
          {/* Feather lines */}
          <path d="M26 29 L12 22 M26 31 L10 28 M24 33 L13 33 M38 29 L52 22 M38 31 L54 28 M40 33 L51 33" {...engrave} />
        </>
      );
  }
}
