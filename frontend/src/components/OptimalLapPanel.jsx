import { useEffect, useMemo, useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useLanguage } from '../context/LanguageContext';
import { analyzeOptimalLap, isCancelled } from '../api/optimalLap';
import { setLibraryExtra } from '../api/library';
import { Panel, Stat, Badge, EmptyState, Icon } from './ui';
import { ChartTooltip, SeriesLegend } from './chartKit';
import { COLOR, TICK, AXIS_LINE, GRID_PROPS, CURSOR, fmtDist } from './chartTheme';
import { cornerLabel, cornerNameMap } from '../utils/cornerLabel';
import css from './OptimalLapPanel.module.css';

const MICRO_SIZES = [10, 25, 50, 100];
const VIEWS = ['cumulative', 'perMicro', 'speed'];

const fmt = (s, vars) => String(s ?? '').replace(/\{(\w+)\}/g, (_, k) => (vars?.[k] ?? `{${k}}`));
const secs = (v, d = 3) => `${Math.abs(v).toFixed(d)}`;

// Heat ramp neutral -> warn -> bad, built with color-mix on theme tokens so it follows light/dark.
const mix = (to, from, t) => `color-mix(in srgb, var(${to}) ${Math.round(t * 100)}%, var(${from}))`;
function heat(t) {
  return t < 0.5 ? mix('--warn', '--heat-neutral', t * 2) : mix('--bad', '--warn', (t - 0.5) * 2);
}

function useOptimalLap(file, lang, microsectorM, attempt) {
  const key = file ? `${file.name}|${file.size}|${file.lastModified}|${lang}|${microsectorM}|${attempt}` : null;
  const [state, setState] = useState(null);

  useEffect(() => {
    if (!file) return undefined;
    const ctrl = new AbortController();
    // Joins the request the app already started right after the upload (see prefetchOptimalLap).
    analyzeOptimalLap(file, lang, { microsectorM, signal: ctrl.signal, fresh: attempt > 0 })
      .then((data) => setState({ key, data }))
      .catch((error) => {
        if (isCancelled(error)) return;
        setState({ key, error: error.message || String(error) });
      });
    return () => ctrl.abort();
  }, [file, lang, microsectorM, key, attempt]);

  if (!key) return { status: 'idle' };
  if (!state || state.key !== key) return { status: 'loading' };
  if (state.error) return { status: 'error', error: state.error };
  return { status: 'ready', data: state.data };
}

function TrackHeat({ data, active, onHover, hovered }) {
  const { t } = useLanguage();
  const geom = useMemo(() => {
    const track = data.track || [];
    if (track.length < 3) return null;
    const xs = track.map((p) => p.x);
    const ys = track.map((p) => p.y);
    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const W = 600, H = 360, PAD = 28;
    const scale = Math.min((W - PAD * 2) / (xMax - xMin || 1), (H - PAD * 2) / (yMax - yMin || 1));
    const offX = PAD + (W - PAD * 2 - (xMax - xMin) * scale) / 2;
    const offY = PAD + (H - PAD * 2 - (yMax - yMin) * scale) / 2;
    const pts = track.map((p) => ({ x: offX + (p.x - xMin) * scale, y: offY + (yMax - p.y) * scale }));
    const gains = data.microsectors.map((m) => m.gain_realistic_s).filter((g) => g > 0).sort((a, b) => a - b);
    const max = gains.length ? gains[Math.min(gains.length - 1, Math.floor(gains.length * 0.95))] : 0.001;
    return { pts, max: Math.max(max, 0.001), W, H };
  }, [data]);

  if (!geom) return <EmptyState icon="map">{t.optLapNoTrack}</EmptyState>;
  const { pts, max, W, H } = geom;
  const micro = data.microsectors;
  const inZone = (m) => active && m.d_end > active.d_start && m.d_start < active.d_end;
  const info = hovered != null ? micro[hovered] : null;

  return (
    <div className={css.mapWrap}>
      <svg viewBox={`0 0 ${W} ${H}`} className={css.map} role="img" aria-label={t.optLapMapAria}>
        <g strokeLinecap="round" strokeLinejoin="round" fill="none">
          {micro.map((m) => (pts[m.index + 1] && inZone(m)) && (
            <line key={`z${m.index}`} x1={pts[m.index].x} y1={pts[m.index].y} x2={pts[m.index + 1].x} y2={pts[m.index + 1].y}
              stroke="var(--ink-1)" strokeOpacity="0.45" strokeWidth="13" />
          ))}
          {micro.map((m) => pts[m.index + 1] && (
            <line key={m.index} x1={pts[m.index].x} y1={pts[m.index].y} x2={pts[m.index + 1].x} y2={pts[m.index + 1].y}
              stroke={heat(Math.min(1, Math.max(0, m.gain_realistic_s) / max))} strokeWidth="7"
              onMouseEnter={() => onHover(m.index)} onMouseLeave={() => onHover(null)} />
          ))}
        </g>
        <circle cx={pts[0].x} cy={pts[0].y} r="5" fill={COLOR.ok} stroke="var(--map-halo)" strokeWidth="2" />
        <text x={pts[0].x + 9} y={pts[0].y + 4} fill={COLOR.ok} className={css.mapLabel}>S/F</text>
      </svg>
      <div className={css.mapLegend}>
        <span>0 ms</span>
        <span className={css.ramp} style={{ background: `linear-gradient(90deg, ${heat(0)}, ${heat(0.5)}, ${heat(1)})` }} />
        <span>{(max * 1000).toFixed(0)} ms</span>
        <span className={css.mapLegendTxt}>{t.optLapMapLegend}</span>
      </div>
      <div className={css.mapInfo} aria-live="polite">
        {info
          ? fmt(t.optLapMapInfo, { from: info.d_start.toFixed(0), to: info.d_end.toFixed(0), gain: (info.gain_realistic_s * 1000).toFixed(0), lap: info.lap_realistic })
          : t.optLapMapHover}
      </div>
    </div>
  );
}

function MainChart({ data, view }) {
  const { t } = useLanguage();
  const cum = data.series.cumulative;
  const sp = data.series.speed_profile;
  const L = data.track_length_m;

  const cumData = useMemo(() => cum.distance.map((d, i) => ({
    d, real: cum.gain_realistic_s[i], theo: cum.gain_theoretical_s[i],
  })), [cum]);
  const microData = useMemo(() => data.microsectors.map((m) => ({
    d: (m.d_start + m.d_end) / 2, real: m.gain_realistic_s, theo: m.gain_theoretical_s,
  })), [data]);
  const speedData = useMemo(() => sp.distance.map((d, i) => ({
    d, best: sp.best_lap[i], real: sp.optimal_realistic[i],
  })), [sp]);

  const names = { real: t.optLapSerRealistic, theo: t.optLapSerTheoretical, best: t.optLapSerBest };
  const axisX = (
    <XAxis dataKey="d" type="number" domain={[0, L]} tick={TICK} axisLine={AXIS_LINE} tickLine={false}
      tickFormatter={fmtDist} height={30} label={{ value: t.optLapAxisDistance, position: 'insideBottom', offset: -2, fill: COLOR.ink3, fontSize: 11 }} />
  );
  const margin = { top: 8, right: 12, left: 0, bottom: 6 };

  const caption = { cumulative: t.optLapAxisGain, perMicro: t.optLapAxisPerMicro, speed: t.optLapAxisSpeed }[view];
  let legend; let chart;
  if (view === 'speed') {
    legend = [{ key: 'best', color: COLOR.ink2, label: t.optLapSerBest }, { key: 'real', color: COLOR.accent, label: t.optLapSerRealistic }];
    chart = (
      <LineChart data={speedData} margin={margin}>
        <CartesianGrid {...GRID_PROPS} />
        {axisX}
        <YAxis tick={TICK} axisLine={false} tickLine={false} width={44} domain={['auto', 'auto']} />
        <Tooltip content={<ChartTooltip unit=" km/h" digits={0} nameMap={names} />} cursor={CURSOR} />
        <Line dataKey="best" stroke={COLOR.ink2} strokeWidth={1.4} dot={false} isAnimationActive={false} connectNulls />
        <Line dataKey="real" stroke={COLOR.accent} strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />
      </LineChart>
    );
  } else if (view === 'perMicro') {
    legend = [{ key: 'real', color: COLOR.accent, label: t.optLapSerRealistic }, { key: 'theo', color: COLOR.warn, label: t.optLapSerTheoretical }];
    chart = (
      <BarChart data={microData} margin={margin} barGap={0}>
        <CartesianGrid {...GRID_PROPS} />
        {axisX}
        <YAxis tick={TICK} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => `${(v * 1000).toFixed(0)}`} />
        <ReferenceLine y={0} stroke={COLOR.lineStrong} />
        <Tooltip content={<ChartTooltip nameMap={names} valueFormatter={(v) => `${(v * 1000).toFixed(0)} ms`} />} cursor={{ fill: COLOR.line, fillOpacity: 0.5 }} />
        <Bar dataKey="theo" fill={COLOR.warn} fillOpacity={0.45} isAnimationActive={false} />
        <Bar dataKey="real" fill={COLOR.accent} isAnimationActive={false} />
      </BarChart>
    );
  } else {
    legend = [{ key: 'real', color: COLOR.accent, label: t.optLapSerRealistic }, { key: 'theo', color: COLOR.warn, label: t.optLapSerTheoretical }];
    chart = (
      <LineChart data={cumData} margin={margin}>
        <CartesianGrid {...GRID_PROPS} />
        {axisX}
        <YAxis tick={TICK} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => `${v.toFixed(1)}`} />
        <Tooltip content={<ChartTooltip unit=" s" digits={3} nameMap={names} />} cursor={CURSOR} />
        <Line dataKey="theo" stroke={COLOR.warn} strokeWidth={1.6} strokeDasharray="5 3" dot={false} isAnimationActive={false} />
        <Line dataKey="real" stroke={COLOR.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    );
  }

  return (
    <div>
      <SeriesLegend items={legend} />
      <div className={css.caption}>{caption}</div>
      <div className={css.chart}>
        <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>
      </div>
    </div>
  );
}

function CornersChart({ data }) {
  const { t } = useLanguage();
  const nameOf = cornerNameMap(data.corners);
  const rows = data.corners.map((c) => ({
    name: c.corner_number, real: c.gain_realistic_s, theo: c.gain_theoretical_s,
  }));
  if (!rows.length) return null;
  const names = { real: t.optLapSerRealistic, theo: t.optLapSerTheoretical };
  return (
    <div>
      <div className="ui-eyebrow">{t.optLapCornersTitle}</div>
      <SeriesLegend items={[
        { key: 'real', color: COLOR.accent, label: t.optLapSerRealistic },
        { key: 'theo', color: COLOR.warn, label: t.optLapSerTheoretical },
      ]} />
      <div className={css.chartSm}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 6, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid {...GRID_PROPS} />
            <XAxis dataKey="name" tick={TICK} axisLine={AXIS_LINE} tickLine={false} height={26} />
            <YAxis tick={TICK} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => v.toFixed(1)} />
            <Tooltip
              content={<ChartTooltip nameMap={names} valueFormatter={(v) => `${v.toFixed(3)} s`}
                labelFormatter={(l) => cornerLabel(t, l, nameOf[l])} />}
              cursor={{ fill: COLOR.line, fillOpacity: 0.5 }}
            />
            <Bar dataKey="theo" fill={COLOR.warn} fillOpacity={0.45} radius={[2, 2, 0, 0]} maxBarSize={18} isAnimationActive={false} />
            <Bar dataKey="real" fill={COLOR.accent} radius={[2, 2, 0, 0]} maxBarSize={18} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ZonesTable({ zones, active, onActive }) {
  const { t } = useLanguage();
  if (!zones.length) return <EmptyState icon="check">{t.optLapNoZones}</EmptyState>;
  return (
    <div className={css.tableWrap}>
      <table className="ui-table">
        <thead>
          <tr>
            <th style={{ width: 36 }}>#</th>
            <th>{t.optLapColZone}</th>
            <th>{t.optLapColCorner}</th>
            <th className="is-num">{t.optLapColLoss}</th>
            <th className="is-num">{t.optLapColLossTheo}</th>
            <th>{t.optLapColLap}</th>
            <th>{t.optLapColTip}</th>
          </tr>
        </thead>
        <tbody>
          {zones.map((z) => (
            <tr
              key={z.rank}
              className={active?.rank === z.rank ? css.rowActive : undefined}
              onMouseEnter={() => onActive(z)} onMouseLeave={() => onActive(null)}
              onFocus={() => onActive(z)} onBlur={() => onActive(null)} tabIndex={0}
            >
              <td className="num">{z.rank}</td>
              <td className={`num ${css.nowrap}`}>{z.d_start.toFixed(0)} - {z.d_end.toFixed(0)} m</td>
              <td className={css.nowrap}>{z.corner_number != null ? <Badge>{cornerLabel(t, z.corner_number, z.corner_name)}</Badge> : (z.corner_label ? <Badge>{z.corner_label}</Badge> : '-')}</td>
              <td className="is-num" style={{ color: 'var(--bad)' }}>{secs(z.loss_realistic_s)} s</td>
              <td className="is-num" style={{ color: 'var(--ink-3)' }}>{secs(z.loss_theoretical_s)} s</td>
              <td className={css.nowrap}><Badge tone="accent">{fmt(t.optLapKpiBestHint, { n: z.donor_lap })}</Badge></td>
              <td className={css.tip}>{z.hint}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Contributions({ data }) {
  const { t } = useLanguage();
  const rows = data.lap_contributions.slice(0, 6);
  const max = Math.max(...rows.map((r) => r.microsectors_realistic), 1);
  return (
    <div>
      <div className="ui-eyebrow">{t.optLapContribTitle}</div>
      <ul className={css.contrib}>
        {rows.map((r) => (
          <li key={r.lap_number} className={css.contribRow}>
            <span className={css.contribLap}>
              {fmt(t.optLapKpiBestHint, { n: r.lap_number })}
              {r.is_best && <Badge tone="ok">{t.optLapContribBest}</Badge>}
            </span>
            <span className={css.contribBar}>
              <span style={{ width: `${(r.microsectors_realistic / max) * 100}%` }} />
            </span>
            <span className={css.contribTxt}>
              {fmt(t.optLapContribRow, { n: r.microsectors_realistic, pct: r.pct_realistic.toFixed(0) })}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Body({ data }) {
  const { t } = useLanguage();
  const [view, setView] = useState('cumulative');
  const [hovered, setHovered] = useState(null);
  const [zone, setZone] = useState(null);
  const best = data.best_lap;
  const real = data.optimal_realistic;
  const theo = data.optimal_theoretical;
  const viewLabels = { cumulative: t.optLapViewCumulative, perMicro: t.optLapViewPerMicro, speed: t.optLapViewSpeed };

  return (
    <>
      <div className={css.kpis}>
        <Stat label={t.optLapKpiBest} value={best.time_str} hint={fmt(t.optLapKpiBestHint, { n: best.lap_number })} />
        <Stat label={t.optLapKpiRealistic} value={real.time_str} tone="accent"
          hint={fmt(t.optLapKpiRealisticHint, { gain: secs(real.gain_s), n: real.n_switches })} />
        <Stat label={t.optLapKpiTheoretical} value={theo.time_str}
          hint={fmt(t.optLapKpiTheoreticalHint, { gain: secs(theo.gain_s) })} />
        <Stat label={t.optLapKpiGain} value={`-${secs(real.gain_s)} s`} tone="ok"
          hint={fmt(t.optLapKpiGainHint, { gain: secs(theo.gain_s) })} />
      </div>

      <div className={css.why}>
        <Icon name="info" size={16} />
        <div>
          <div className={css.whyTitle}>{t.optLapWhyTitle}</div>
          <p>{data.explanation}</p>
        </div>
      </div>

      {data.warnings?.length > 0 && (
        <ul className={css.warnings}>
          {data.warnings.map((w) => <li key={w}><Badge tone="warn">{w}</Badge></li>)}
        </ul>
      )}

      <div className={css.grid}>
        <div className={css.col}>
          <div role="group" aria-label={t.optLapViewAria} className={css.views}>
            <div className="ui-seg">
              {VIEWS.map((v) => (
                <button key={v} type="button" className="ui-seg__item" aria-pressed={view === v} onClick={() => setView(v)}>
                  {viewLabels[v]}
                </button>
              ))}
            </div>
          </div>
          <MainChart data={data} view={view} />
        </div>
        <div className={css.col}>
          <div className="ui-eyebrow">{t.optLapMapTitle}</div>
          <TrackHeat data={data} active={zone} hovered={hovered} onHover={setHovered} />
        </div>
      </div>

      <div className={css.section}>
        <div className="ui-eyebrow">{t.optLapZonesTitle}</div>
        <ZonesTable zones={data.top_zones} active={zone} onActive={setZone} />
      </div>

      <div className={`${css.grid} ${css.section}`}>
        <CornersChart data={data} />
        <Contributions data={data} />
      </div>

      <div className={css.meta}>
        <span>{fmt(t.optLapMeta, { n: data.n_laps_used, k: data.n_microsectors, m: data.params.microsector_m })}</span>
        {data.laps_excluded.length > 0 && (
          <span title={data.laps_excluded.map((e) => `${fmt(t.optLapExcludedLap, { n: e.lap_number })}: ${e.reason}`).join('\n')}>
            <Badge>{fmt(t.optLapExcluded, { n: data.laps_excluded.length })}</Badge>
          </span>
        )}
      </div>
    </>
  );
}

/** Optimal lap built from the best microsectors. Loads in the background once mounted. */
export default function OptimalLapPanel({ file, preloaded = null }) {
  const { t, lang } = useLanguage();
  const [microsectorM, setMicrosectorM] = useState(25);
  const [attempt, setAttempt] = useState(0);
  const live = useOptimalLap(preloaded ? null : file, lang, microsectorM, attempt);
  const res = preloaded ? { status: 'ready', data: preloaded } : live;

  // Registers the result so "Save to library" stores it with the session.
  const liveData = live.status === 'ready' && live.data?.available ? live.data : null;
  useEffect(() => {
    if (preloaded) return undefined;
    setLibraryExtra('optimal_lap', liveData);
    return () => setLibraryExtra('optimal_lap', null);
  }, [preloaded, liveData]);

  const sizeControl = (
    <div role="group" aria-label={t.optLapMicroSize} className="ui-seg" title={t.optLapMicroSize}>
      {MICRO_SIZES.map((m) => (
        <button key={m} type="button" className="ui-seg__item" aria-pressed={microsectorM === m} onClick={() => setMicrosectorM(m)}>
          {m} m
        </button>
      ))}
    </div>
  );

  let body;
  if (res.status === 'loading') {
    body = (
      <div className={css.loading} role="status" aria-live="polite">
        <span className="shell-spin" />
        <span>{t.optLapLoading}</span>
      </div>
    );
  } else if (res.status === 'error') {
    body = (
      <div className={css.error} role="alert">
        <Icon name="alert" size={16} />
        <div>
          <div className={css.errorTitle}>{t.optLapErrorTitle}</div>
          <div>{res.error}</div>
        </div>
        <button type="button" className="ui-btn ui-btn--sm" onClick={() => setAttempt((a) => a + 1)}>{t.optLapRetry}</button>
      </div>
    );
  } else if (res.status === 'ready' && !res.data?.available) {
    body = <EmptyState icon="info">{res.data?.reason || t.optLapUnavailable}</EmptyState>;
  } else if (res.status === 'ready') {
    body = <Body data={res.data} />;
  } else {
    body = <EmptyState icon="info">{t.optLapUnavailable}</EmptyState>;
  }

  return (
    <Panel id="optimal-lap" icon="stopwatch" title={t.optLapTitle} subtitle={t.optLapSub} actions={preloaded ? undefined : sizeControl}>
      {body}
    </Panel>
  );
}
