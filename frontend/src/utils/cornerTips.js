// Tooltip texts for the unified corner map (plain functions of the i18n object `t`).
import { BADGE_KINDS, confidenceLevel, kindOf, sourceParts } from './cornerKind';

/** Confidence tooltip: what backs the corner (braking, geometry, table) or just the percentage. */
export function confidenceTip(t, c) {
  const v = c?.confidence;
  if (typeof v !== 'number') return '';
  const pct = Math.round(v * 100);
  let txt;
  if (c.sources?.length) {
    const { parts, telemetry } = sourceParts(c.sources);
    if (!telemetry) txt = t.cmConfGeom(pct);
    else {
      const names = parts.map((p) => t[`cmSrc_${p}`]);
      const list = names.length > 1 ? `${names.slice(0, -1).join(', ')} ${t.cmAnd} ${names[names.length - 1]}` : names.join('');
      txt = t.cmConfBacked(pct, list);
    }
  } else {
    txt = t.cmConfGeneric(pct);
  }
  return confidenceLevel(c) === 'low' ? `${txt} ${t.cmConfCare}` : txt;
}

/** Plain-text help for a corner kind (empty for ordinary braking corners). */
export function kindTip(t, c) {
  const k = kindOf(c);
  return BADGE_KINDS.includes(k) ? t[`cmKindTip_${k}`] : '';
}

/** Chicane / esses detail: "Compound corner with 2 apexes at 710 m, 745 m". */
export function complexTip(t, c) {
  const subs = c?.sub_apexes || [];
  const list = subs.map((s) => `${Math.round(s.distance_m)} m`).join(', ');
  return t.cmComplexTip(subs.length || 2, list);
}

/** True when the corner should render attenuated (confidence below 0.6). */
export const isDim = (c) => confidenceLevel(c) === 'low';
