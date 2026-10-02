import { useId, useMemo, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Icon, Badge } from './ui';
import styles from './DataQualityPanel.module.css';

const LEVEL_TONE = { good: 'ok', fair: 'warn', poor: 'bad' };
const CH_TONE = { ok: 'ok', missing: undefined, constant: 'warn', synthesized: 'warn', partial: 'warn', sparse: 'warn', inactive: 'warn' };
const MOD_TONE = { ok: 'ok', degraded: 'warn', unavailable: 'bad' };
const PRIO_TONE = { high: 'bad', medium: 'warn', low: undefined };

function ScoreRing({ score, level, label }) {
  const r = 15;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <span className={`${styles.ring} ${styles[`lv_${level}`]}`} role="img" aria-label={label}>
      <svg width="38" height="38" viewBox="0 0 38 38" aria-hidden="true">
        <circle cx="19" cy="19" r={r} className={styles.ringTrack} />
        <circle
          cx="19" cy="19" r={r} className={styles.ringArc}
          strokeDasharray={`${c * pct} ${c}`} transform="rotate(-90 19 19)"
        />
      </svg>
      <span className={styles.ringNum}>{score}</span>
    </span>
  );
}

function fmtDuration(s) {
  if (s == null) return null;
  const total = Math.round(s);
  const m = Math.floor(total / 60);
  const sec = total % 60;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function Meta({ label, children }) {
  if (children == null || children === '') return null;
  return (
    <div className={styles.meta}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Body({ dq, id }) {
  const { t, lang } = useLanguage();
  const [showAll, setShowAll] = useState(false);
  const src = dq.source ?? {};
  const laps = dq.laps ?? {};
  const label = (kind, key, fallback) => t[`dqui_${kind}_${key}`] ?? fallback ?? key;

  const channels = useMemo(() => {
    const rank = (c) => (c.status === 'ok' ? 1 : 0);
    return [...(dq.channels ?? [])].sort((a, b) => rank(a) - rank(b) || b.importance - a.importance);
  }, [dq.channels]);
  const issues = channels.filter((c) => c.status !== 'ok');
  const rows = showAll || issues.length === 0 ? channels : issues;
  const nf = new Intl.NumberFormat(lang === 'es' ? 'es-ES' : 'en-US');
  const unknown = t.dqui_unknown;

  return (
    <div id={id} className={styles.body}>
      <dl className={styles.metaGrid}>
        <Meta label={t.dqui_srcSim}>{src.sim_label}</Meta>
        <Meta label={t.dqui_srcCar}>{src.car}</Meta>
        <Meta label={t.dqui_srcCircuit}>{src.circuit}</Meta>
        <Meta label={t.dqui_srcMode}>{t[`dqui_mode_${src.mode}`] ?? src.mode}</Meta>
        <Meta label={t.dqui_srcRate}>{src.sample_rate_hz != null ? `${src.sample_rate_hz} Hz` : unknown}</Meta>
        <Meta label={t.dqui_srcDuration}>{fmtDuration(src.duration_s)}</Meta>
        <Meta label={t.dqui_srcSamples}>{src.n_samples != null ? nf.format(src.n_samples) : null}</Meta>
        <Meta label={t.dqui_srcChannels}>{src.n_channels}</Meta>
        <Meta label={t.dqui_srcClock}>{src.time_clock}</Meta>
      </dl>

      <section className={styles.sec} aria-label={t.dqui_secLaps}>
        <h4 className={styles.secTitle}>{t.dqui_secLaps}</h4>
        <ul className={styles.lapStats}>
          <li><b>{laps.detected}</b> {t.dqui_lapsDetected}</li>
          <li className={laps.sufficient === false ? styles.warnTxt : undefined}><b>{laps.valid}</b> {t.dqui_lapsValid}</li>
          <li><b>{laps.pit}</b> {t.dqui_lapsPit}</li>
          <li><b>{laps.outliers}</b> {t.dqui_lapsOutliers}</li>
          <li><b>{laps.partial_discarded}</b> {t.dqui_lapsPartial}</li>
          <li>{t.dqui_lapsSegmentation}: <b>{t[`dqui_seg_${laps.segmentation}`] ?? t.dqui_seg_unknown}</b></li>
        </ul>
      </section>

      <section className={styles.sec} aria-label={t.dqui_secImprove}>
        <h4 className={styles.secTitle}>{t.dqui_secImprove}</h4>
        {dq.improvements?.length ? (
          <ol className={styles.fixes}>
            {dq.improvements.map((f) => (
              <li key={f.id} className={styles.fix}>
                <div className={styles.fixHead}>
                  <Badge tone={PRIO_TONE[f.priority]}>{t[`dqui_prio_${f.priority}`]}</Badge>
                  <span className={styles.fixTitle}>{f.title}</span>
                </div>
                <p className={styles.fixText}>{f.detail}</p>
                {f.unlocks?.length > 0 && (
                  <p className={styles.fixUnlocks}>
                    <span>{t.dqui_unlocks}:</span>{' '}
                    {f.unlocks.map((m) => label('mod', m)).join(' · ')}
                  </p>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className={styles.note}>{t.dqui_noImprove}</p>
        )}
      </section>

      <section className={styles.sec} aria-label={t.dqui_secModules}>
        <h4 className={styles.secTitle}>{t.dqui_secModules}</h4>
        <ul className={styles.mods}>
          {(dq.modules ?? []).map((m) => (
            <li key={m.key} className={styles.mod}>
              <span className={styles.modBadge}>
                <Badge tone={MOD_TONE[m.status]} title={t[m.source === 'module' ? 'dqui_src_module' : 'dqui_src_channels']}>
                  {t[`dqui_mst_${m.status}`]}
                </Badge>
              </span>
              <span className={styles.modMain}>
                <span className={styles.modName}>{label('mod', m.key, m.label)}</span>
                {m.reason && <span className={styles.modReason}>{m.reason}</span>}
                {m.details?.length > 0 && (
                  <ul className={styles.modDetails}>
                    {m.details.map((d) => <li key={d}>{d}</li>)}
                  </ul>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.sec} aria-label={t.dqui_secChannels}>
        <h4 className={styles.secTitle}>
          {t.dqui_secChannels}
          {issues.length > 0 && (
            <button type="button" className={styles.linkBtn} onClick={() => setShowAll((v) => !v)}>
              {showAll ? t.dqui_onlyIssues : t.dqui_showAll(channels.length)}
            </button>
          )}
        </h4>
        {issues.length === 0 && <p className={styles.note}>{t.dqui_allOkNote}</p>}
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{t.dqui_colChannel}</th>
                <th scope="col">{t.dqui_colStatus}</th>
                <th scope="col">{t.dqui_colDetail}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.key} className={c.status === 'ok' ? styles.rowOk : undefined}>
                  <th scope="row">{label('ch', c.key, c.label)}</th>
                  <td><Badge tone={CH_TONE[c.status]}>{t[`dqui_st_${c.status}`] ?? c.status}</Badge></td>
                  <td className={styles.detail}>{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={styles.sec} aria-label={t.dqui_secBreakdown}>
        <h4 className={styles.secTitle}>{t.dqui_secBreakdown}</h4>
        <ul className={styles.breakdown}>
          {['channels', 'laps', 'modules'].map((k) => (
            <li key={k}>
              <span>{t[`dqui_bd_${k}`]}</span>
              <span className={styles.bar} aria-hidden="true"><i style={{ width: `${dq.breakdown?.[k]?.score ?? 0}%` }} /></span>
              <b>{dq.breakdown?.[k]?.score ?? 0}</b>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/**
 * Collapsible data-quality band shown above the results.
 * Props: session / compare = `data_quality` objects returned by the backend (either may be null).
 */
export default function DataQualityPanel({ session, compare }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [pick, setPick] = useState(null);
  const bodyId = useId();

  const both = !!(session && compare);
  const active = pick === 'session' && session ? 'session' : pick === 'compare' && compare ? 'compare' : (compare ? 'compare' : 'session');
  const dq = active === 'compare' ? compare : session;
  if (!dq || dq.available === false) return null;

  const cs = dq.channel_summary ?? {};
  const ms = dq.module_summary ?? {};
  const limited = (ms.degraded ?? 0) + (ms.unavailable ?? 0);
  const quiet = dq.level === 'good' && limited === 0 && !(dq.improvements?.length);
  const levelTxt = t[`dqui_level_${dq.level}`];
  const top = dq.improvements?.[0];

  return (
    <section id="data-quality" className={`${styles.root} ${styles[`lv_${dq.level}`]}`} aria-label={t.dqui_region}>
      <div className={styles.barRow}>
        <button
          type="button"
          className={`${styles.toggle}${quiet ? ` ${styles.toggleQuiet}` : ''}`}
          aria-expanded={open}
          aria-controls={bodyId}
          title={open ? t.dqui_collapse : t.dqui_expand}
          onClick={() => setOpen((v) => !v)}
        >
          {quiet ? (
            <>
              <span className={styles.quietIcon}><Icon name="check" size={14} /></span>
              <span className={styles.quietText}>{t.dqui_title}: {t.dqui_allGood}</span>
              <span className={styles.quietScore}>{dq.score}/100</span>
            </>
          ) : (
            <>
              <ScoreRing score={dq.score} level={dq.level} label={t.dqui_scoreAria(dq.score)} />
              <span className={styles.head}>
                <span className={styles.title}>{t.dqui_title}</span>
                <Badge tone={LEVEL_TONE[dq.level]}>{levelTxt}</Badge>
              </span>
              <span className={styles.chips}>
                <Badge tone="ok">{t.dqui_chipOk(cs.ok ?? 0)}</Badge>
                {cs.warning > 0 && <Badge tone="warn">{t.dqui_chipWarn(cs.warning)}</Badge>}
                {cs.missing > 0 && <Badge>{t.dqui_chipMissing(cs.missing)}</Badge>}
                {limited > 0 && <Badge tone={ms.unavailable > 0 ? 'bad' : 'warn'}>{t.dqui_chipLimited(limited)}</Badge>}
              </span>
              {top && <span className={styles.top} title={top.detail}>{t.dqui_topFix}: {top.title}</span>}
            </>
          )}
          <Icon name="chevron" size={14} className={`${styles.chev}${open ? ` ${styles.chevOpen}` : ''}`} />
        </button>
        {both && (
          <div className="ui-seg" role="group" aria-label={t.dqui_title}>
            <button type="button" className="ui-seg__item" aria-pressed={active === 'session'} onClick={() => setPick('session')}>{t.dqui_tabSession}</button>
            <button type="button" className="ui-seg__item" aria-pressed={active === 'compare'} onClick={() => setPick('compare')}>{t.dqui_tabCompare}</button>
          </div>
        )}
      </div>
      {open && <Body key={active} dq={dq} id={bodyId} />}
    </section>
  );
}
