import { useLanguage } from '../context/LanguageContext';
import { Badge, Icon } from './ui';
import { BADGE_KINDS, confidenceLevel, kindOf, isNoPhase } from '../utils/cornerKind';
import { confidenceTip, kindTip, complexTip } from '../utils/cornerTips';
import css from './CornerMeta.module.css';

export function KindBadge({ corner }) {
  const { t } = useLanguage();
  const k = kindOf(corner);
  if (!BADGE_KINDS.includes(k)) return null;
  return <Badge tone={k === 'lift' ? 'warn' : 'accent'} title={kindTip(t, corner)}>{t[`cmKind_${k}`]}</Badge>;
}

export function DirIcon({ corner, size = 14 }) {
  const { t } = useLanguage();
  const d = corner?.direction;
  if (d !== 'left' && d !== 'right') return null;
  const label = d === 'left' ? t.cmDirLeft : t.cmDirRight;
  const radius = typeof corner.min_radius_m === 'number' ? ` · ${t.cmRadius(corner.min_radius_m)}` : '';
  return (
    <span className={css.dir} title={`${label}${radius}`} role="img" aria-label={label}>
      <Icon name={d === 'left' ? 'turnLeft' : 'turnRight'} size={size} />
    </span>
  );
}

export function ComplexBadge({ corner }) {
  const { t } = useLanguage();
  if (!corner?.is_complex) return null;
  return <Badge title={complexTip(t, corner)}>{t.cmComplex}</Badge>;
}

/** Discreet confidence marker: nothing when high, a dot when medium or low. */
export function ConfDot({ corner }) {
  const { t } = useLanguage();
  const lvl = confidenceLevel(corner);
  if (lvl !== 'low' && lvl !== 'mid') return null;
  const label = lvl === 'low' ? t.cmConfLow : t.cmConfMid;
  return (
    <span
      className={`${css.conf} ${lvl === 'low' ? css.confLow : css.confMid}`}
      title={confidenceTip(t, corner)}
      role="img"
      aria-label={label}
    />
  );
}

/** Direction + kind + chicane + confidence, in one compact inline group. Renders nothing for legacy payloads. */
export function CornerTags({ corner }) {
  const k = kindOf(corner);
  const lvl = confidenceLevel(corner);
  const any = corner && (corner.direction || BADGE_KINDS.includes(k) || corner.is_complex || lvl === 'low' || lvl === 'mid');
  if (!any) return null;
  return (
    <span className={css.tags}>
      <DirIcon corner={corner} />
      <KindBadge corner={corner} />
      <ComplexBadge corner={corner} />
      <ConfDot corner={corner} />
    </span>
  );
}

/** One-line explanation for flat-out / kink corners that have no braking, apex or throttle figures. */
export function NoPhaseNote({ corner }) {
  const { t } = useLanguage();
  if (!isNoPhase(corner)) return null;
  return <p className={css.note}>{kindOf(corner) === 'kink' ? t.cmNoPhasesKink : t.cmNoPhases}</p>;
}

// Backend warning text -> translated text. Unknown texts fall back to the backend wording.
function translateWarnings(t, warnings) {
  const out = [];
  let ignored = 0;
  (warnings || []).forEach((w) => {
    const s = String(w);
    let m;
    if (/^unknown circuit/i.test(s)) out.push({ tone: 'info', text: t.cmWarnUnknownCircuit });
    else if (/^no venue/i.test(s)) out.push({ tone: 'info', text: t.cmWarnNoVenue });
    else if ((m = s.match(/^only (\d+) lap/i))) out.push({ tone: 'info', text: t.cmWarnFewLaps(Number(m[1])) });
    else if ((m = s.match(/measured length (\d+) m does not fit/i))) out.push({ tone: 'warn', text: t.cmWarnLength(m[1]) });
    else if (/^lap \S+: /i.test(s) && /ignored/i.test(s)) ignored += 1;
    else if (/^no usable laps/i.test(s)) out.push({ tone: 'warn', text: t.cmWarnNoLaps });
    else out.push({ tone: 'info', text: s });
  });
  if (ignored) out.push({ tone: 'info', text: t.cmWarnLapIgnored(ignored) });
  return out;
}

/**
 * Corner-map summary line (corners, names, laps, method with tooltip) plus compact notices for
 * `corner_map.warnings`. Renders nothing without a `corner_map` (legacy detection).
 */
export function CornerMapNotice({ cornerMap }) {
  const { t } = useLanguage();
  if (!cornerMap || typeof cornerMap !== 'object') return null;
  const warns = translateWarnings(t, cornerMap.warnings);
  const tpl = String(cornerMap.method || '').includes('template');
  const hasMethod = !!cornerMap.method;
  return (
    <div className={css.notice} data-testid="corner-map-notice">
      <div className={css.noticeRow}>
        <span className={css.noticeTitle}>{t.cmMapTitle}</span>
        {cornerMap.n_corners != null && (
          <span className={css.noticeTxt}>{t.cmMapSummary(cornerMap.n_corners, cornerMap.n_named ?? 0)}</span>
        )}
        {cornerMap.n_laps != null && <span className={css.noticeTxt}>{t.cmMapLaps(cornerMap.n_laps)}</span>}
        {hasMethod && (
          <Badge tone={tpl ? 'ok' : undefined} title={tpl ? t.cmMethodTemplateTip : t.cmMethodConsensusTip}>
            {tpl ? t.cmMethodTemplate : t.cmMethodConsensus}
          </Badge>
        )}
      </div>
      {warns.map((w, i) => (
        <div key={i} className={`${css.warn} ${w.tone === 'warn' ? css.warnTone : ''}`} role="note">
          <Icon name={w.tone === 'warn' ? 'alert' : 'info'} size={14} />
          <span>{w.text}</span>
        </div>
      ))}
    </div>
  );
}
