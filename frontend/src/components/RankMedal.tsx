import { type ReactNode, useId } from "react";

import type { RankName } from "../ranks";

/** Each rank is an army-style insignia struck in its own material, from a private's
 * single chevron to a lieutenant colonel's oak leaf, topped by a heraldic eagle:
 *   Bronze      Private               1 chevron
 *   Silver      Private First Class   1 chevron, 1 rocker
 *   Gold        Corporal              2 chevrons
 *   Platinum    Sergeant              3 chevrons
 *   Diamond     First Sergeant        3 chevrons, 2 rockers, a diamond
 *   Emerald     Sergeant Major        3 chevrons, 3 rockers, a star
 *   Pace Setter Lieutenant Colonel    oak leaf
 *   Apex        (heraldic)            double-headed eagle with a mountain
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

// The Apex: a double-headed eagle with rayed wings (a heraldic form centuries old), with a
// mountain on its breast. Drawn on a 442 x 240 grid, left half only (the right is mirrored
// about x = 221), then scaled into the 64 x 64 badge.
type Pt = [number, number];
const RAY_PIVOT: Pt = [205, 118];
// The wing's outer edge, top to bottom: each pair of neighbours bounds one feather.
const RAY_EDGE: Pt[] = [
  [6, 64], [12, 86], [28, 106], [50, 124], [76, 140], [102, 154], [128, 166], [156, 178],
];
function towardPivot([x, y]: Pt, distance: number): string {
  const [px, py] = RAY_PIVOT;
  const len = Math.hypot(x - px, y - py);
  return `${(px + ((x - px) * distance) / len).toFixed(1)} ${(py + ((y - py) * distance) / len).toFixed(1)}`;
}
const EAGLE_RAYS = RAY_EDGE.slice(0, -1).map((top, i) => {
  const bottom = RAY_EDGE[i + 1];
  // A pointed tip just past the middle of the feather's outer end
  const [mx, my] = [(top[0] + bottom[0]) / 2, (top[1] + bottom[1]) / 2];
  const [nx, ny] = [bottom[1] - top[1], -(bottom[0] - top[0])];
  const n = Math.hypot(nx, ny);
  const tip = `${(mx + (nx / n) * 7).toFixed(1)} ${(my + (ny / n) * 7).toFixed(1)}`;
  return `M${towardPivot(top, 12)} L${top[0]} ${top[1]} L${tip} L${bottom[0]} ${bottom[1]} L${towardPivot(bottom, 12)} Z`;
});
const EAGLE_ARM =
  "M8 60 L158 60 C171 60 180 68 184 80 L190 100 L178 102 L170 84 C167 78 162 76 156 76 L12 76 C7 76 5 70 8 60 Z";
const EAGLE_HEAD =
  "M221 120 L221 102 L212 72 L170 80 L151 83 L142 95 L152 108 L158 96 L175 97 L186 108 L201 116 Z";
const EAGLE_BEAK = "M170 80 L151 83 L142 95 L152 108 L158 96 L175 97 Z";
const EAGLE_CHEST = "M188 104 L254 104 L241 160 L221 188 L201 160 Z";
const CHEST_MOUNTAIN = "M190 180 L207 132 L215 142 L226 110 L254 180 Z";
const CHEST_RIDGES = "M226 110 L221 127 L225 140 M207 132 L208 146 M226 110 L232 124 L229 134";
const EAGLE_TALON = "M209 160 L199 178 L186 194 L195 193 L192 210 L200 199 L203 212 L208 197 L215 176 Z";
const EAGLE_TAIL = "M212 176 L208 214 L221 205 L234 214 L230 176 Z";
const APEX_FIT = `translate(${(1 - 5 * (62 / 432)).toFixed(2)} ${(32 - 136 * (62 / 432)).toFixed(2)}) scale(${(62 / 432).toFixed(4)})`;

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
      <Insignia id={id} rank={rank} metal={metal} engrave={engrave} light={m.light} edge={m.edge} />
    </svg>
  );
}

type Paint = Record<string, string | number>;

function Insignia({
  id,
  rank,
  metal,
  engrave,
  light,
  edge,
}: {
  id: string;
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
    case "Apex": {
      // Drawn on a grid about 7x the badge's, so strokes are scaled to match.
      const line = { ...metal, strokeWidth: 5 };
      const groove = { fill: "none", stroke: edge, strokeWidth: 3.5, strokeLinecap: "round" as const, opacity: 0.75 };
      const mirrored = (children: ReactNode) =>
        [0, 1].map((side) => (
          <g key={side} transform={side ? "translate(442 0) scale(-1 1)" : undefined}>
            {children}
          </g>
        ));
      return (
        <g transform={APEX_FIT}>
          {mirrored(
            <>
              {EAGLE_RAYS.map((d) => <path key={d} d={d} {...line} />)}
              <path d={EAGLE_ARM} {...line} />
            </>,
          )}
          <path d={EAGLE_TAIL} {...line} />
          <path d="M221 180 V208" {...groove} />
          {mirrored(<path d={EAGLE_TALON} {...line} />)}
          <clipPath id={`${id}-chest`}>
            <path d={EAGLE_CHEST} />
          </clipPath>
          <path d={EAGLE_CHEST} {...line} />
          <g clipPath={`url(#${id}-chest)`}>
            <path d={CHEST_MOUNTAIN} fill={light} stroke={edge} strokeWidth="4" strokeLinejoin="round" />
            <path d={CHEST_RIDGES} {...groove} strokeWidth={3} />
          </g>
          <path d={EAGLE_CHEST} fill="none" stroke={edge} strokeWidth="5" strokeLinejoin="round" />
          {mirrored(
            <>
              <path d={EAGLE_HEAD} {...line} />
              <path d={EAGLE_BEAK} fill={light} stroke={edge} strokeWidth="4" strokeLinejoin="round" />
            </>,
          )}
        </g>
      );
    }
  }
}
