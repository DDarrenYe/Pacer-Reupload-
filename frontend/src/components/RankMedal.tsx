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

/** One feather: a long leaf from its root at (x, y), pointing at `angle` degrees, and
 * its shaft (the quill line down the middle). */
function feather(x: number, y: number, angle: number, length: number, width: number) {
  const a = (angle * Math.PI) / 180;
  const [dx, dy] = [Math.cos(a), Math.sin(a)];
  const at = (t: number, side = 0) =>
    `${(x + dx * length * t - dy * side).toFixed(1)} ${(y + dy * length * t + dx * side).toFixed(1)}`;
  const w = width / 2;
  return {
    outline: `M${x} ${y} C${at(0.3, w)} ${at(0.85, w)} ${at(1)} C${at(0.85, -w)} ${at(0.3, -w)} ${x} ${y} Z`,
    shaft: `M${at(0.35)} L${at(0.9)}`,
  };
}
const feathers = (x: number, y: number, angles: number[], lengths: number[], width: number) =>
  angles.map((angle, i) => feather(x, y, angle, lengths[i], width));

// A colonel's eagle, as on the insignia: wings raised, feathers hanging from their leading
// edge, head turned to its right with a hooked beak, the shield as its breast, and an olive
// branch and arrows in its talons. Coordinates are for the left wing; the right is mirrored.
const WING_EDGE = { from: [28, 24], c1: [24, 15], c2: [20, 8], to: [15, 4] } as const;
function onEdge(t: number): [number, number] {
  const { from, c1, c2, to } = WING_EDGE;
  const u = 1 - t;
  const mix = (i: 0 | 1) => u ** 3 * from[i] + 3 * u * u * t * c1[i] + 3 * u * t * t * c2[i] + t ** 3 * to[i];
  return [Number(mix(0).toFixed(1)), Number(mix(1).toFixed(1))];
}
const WING_STEPS = [0.12, 0.24, 0.36, 0.48, 0.6, 0.71, 0.81, 0.9, 0.98];
// Feathers swing from hanging straight down by the body to pointing outwards at the tip,
// and grow longer towards the tip like real primaries.
const EAGLE_PRIMARIES = WING_STEPS.map((t) => feather(...onEdge(t), 100 + 68 * t, 9 + 5.5 * t, 4.2));
const EAGLE_COVERTS = WING_STEPS.map((t) => feather(...onEdge(t), 100 + 68 * t, 5.5, 4.4));
const [WX, WY] = [WING_EDGE.to[0], WING_EDGE.to[1]];
const EAGLE_WING_EDGE =
  `M28 24 C24 15 18 7 ${WX} ${WY} C${WX + 1} ${WY + 3} ${WX + 3} ${WY + 5} ${WX + 5} ${WY + 6} ` +
  "C20 13 24 20 28.5 27 Z";
const EAGLE_TAIL = feathers(32, 40, [66, 78, 90, 102, 114], [10.5, 12, 12.5, 12, 10.5], 4.4);
const EAGLE_BODY = "M27.5 22.5 C26 29 26.8 36 29.5 41.5 L34.5 41.5 C37.2 36 38 29 36.5 22.5 Z";
const EAGLE_SHIELD = "M28.9 26.5 H35.1 V32.5 C35.1 36.4 32 39.4 32 39.4 C32 39.4 28.9 36.4 28.9 32.5 Z";
const EAGLE_HEAD =
  "M35.2 24 C35.6 20.2 35 16.8 33.2 14.9 C31.7 13.3 29 12.8 26.8 13.6 C25.6 14 24.6 14.6 23.8 15 " +
  "L21.6 15.5 C20 15.9 19.7 18 20.9 19.4 C21.1 18.5 21.6 17.9 22.3 17.8 L24.8 17.9 " +
  "C25.6 19.6 26.9 21.1 28.4 21.9 C28.9 22.6 29 23.3 29 24 Z";
const EAGLE_BEAK = "M23.8 15 L21.6 15.5 C20 15.9 19.7 18 20.9 19.4 C21.1 18.5 21.6 17.9 22.3 17.8 L24.8 17.9 C24.5 16.9 24.2 15.9 23.8 15 Z";
const OLIVE_LEAVES: [number, number, number][] = [
  [24.4, 44.6, -25],
  [21.4, 47.4, 25],
  [18.6, 44.9, -25],
  [16, 47.6, 25],
];

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
    case "Apex": {
      const fine = { ...metal, strokeWidth: 0.8 };
      const quill = { ...engrave, strokeWidth: 0.5, opacity: 0.55 };
      return (
        <>
          {[0, 1].map((side) => (
            <g key={side} transform={side ? "translate(64 0) scale(-1 1)" : undefined}>
              {[...EAGLE_PRIMARIES].reverse().map((f) => (
                <g key={f.outline}>
                  <path d={f.outline} {...fine} />
                  <path d={f.shaft} {...quill} />
                </g>
              ))}
              {[...EAGLE_COVERTS].reverse().map((f) => <path key={f.outline} d={f.outline} {...fine} />)}
              <path d={EAGLE_WING_EDGE} {...fine} />
            </g>
          ))}
          {EAGLE_TAIL.map((f) => (
            <g key={f.outline}>
              <path d={f.outline} {...fine} />
              <path d={f.shaft} {...quill} />
            </g>
          ))}
          {/* Legs and talons: an olive branch in its right, arrows in its left */}
          <path d="M29.6 40 L27.2 44.4 M34.4 40 L36.8 44.4" {...engrave} strokeWidth={1.6} opacity={1} />
          <path d="M27.4 44.6 C23.5 45.6 19.5 46.6 14.5 46.2" {...engrave} strokeWidth={0.9} opacity={1} />
          {OLIVE_LEAVES.map(([cx, cy, r]) => (
            <ellipse key={cx} cx={cx} cy={cy} rx="1.9" ry="0.85" transform={`rotate(${r} ${cx} ${cy})`} {...fine} strokeWidth={0.5} />
          ))}
          {[0, 1.8, 3.6].map((dy) => (
            <g key={dy}>
              <path d={`M35.5 ${43 + dy} L48.5 ${45.6 + dy}`} stroke={edge} strokeWidth="0.8" strokeLinecap="round" />
              <path d={`M49.6 ${45.8 + dy} L47.4 ${44.6 + dy} L47.1 ${46.6 + dy} Z`} fill={edge} />
            </g>
          ))}
          <path d="M26.2 44 l1 1.4 M28 44.2 l0.2 1.6 M36 44.2 l-0.2 1.6 M37.8 44 l-1 1.4" {...engrave} strokeWidth={0.7} opacity={1} />
          <path d={EAGLE_BODY} {...fine} />
          {/* The shield is its breast: a light chief over stripes */}
          <path d={EAGLE_SHIELD} {...fine} />
          <path d="M28.9 26.5 H35.1 V28.8 H28.9 Z" fill={light} stroke={edge} strokeWidth="0.5" />
          <path d="M30.4 28.8 V36.6 M32 28.8 V39 M33.6 28.8 V36.6" {...engrave} strokeWidth={0.6} opacity={0.9} />
          <path d={EAGLE_HEAD} {...fine} />
          <path d={EAGLE_BEAK} fill={light} stroke={edge} strokeWidth="0.6" strokeLinejoin="round" />
          <path d="M21.9 16.8 L24.6 17.1" stroke={edge} strokeWidth="0.5" strokeLinecap="round" />
          {/* A low brow over the eye gives the eagle's glare */}
          <path d="M25.6 15 C26.6 14.4 28 14.4 29.2 15" fill="none" stroke={edge} strokeWidth="1" strokeLinecap="round" />
          <circle cx="27.3" cy="16.1" r="0.75" fill={edge} />
          {/* Ruffled neck feathers where the head meets the shield */}
          <path d="M28.8 23.4 l1 -1.5 l0.9 1.6 l0.9 -1.6 l0.9 1.6 l0.9 -1.6 l0.9 1.6 l0.8 -1.4" fill="none" stroke={edge} strokeWidth="0.6" strokeLinejoin="round" opacity="0.8" />
        </>
      );
    }
  }
}
