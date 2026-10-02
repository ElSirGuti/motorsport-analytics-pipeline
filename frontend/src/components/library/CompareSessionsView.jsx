import { useEffect, useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { useLanguage } from '../../context/LanguageContext';
import { EmptyState, Icon, Panel, Stat } from '../ui';
import { ChartTooltip, SeriesLegend } from '../chartKit';
import { ACTIVE_DOT, AXIS_LINE, COLOR, CURSOR, GRID_PROPS, LAP_COLORS, TICK } from '../chartTheme';
import { compareLibrarySessions, listLibrary } from '../../api/library';
import { fmtDate, fmtLap, fmtSigned, isCompatible } from './libUtil';
import css from './Library.module.css';

const fmtAxisLap = (s) => (s > 0 ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}` : '');
const label = (s, lang) => `${s.title} · ${fmtDate(s.created_at, lang)} · ${fmtLap(s.best_lap_s)}`;

function SessionCard({ tag, color, s, lang }) {
  return (
    <div className={css.sessCard} style={{ borderTopColor: color }}>
      <span className={css.sessTag} style={{ color }}>{tag}</span>
      <div className={css.sessBody}>
        <div className={css.title} title={s.title}>{s.title}</div>
        <div className={css.file}>{[s.venue, s.vehicle].filter(Boolean).join(' · ') || '—'}</div>
        <div className={css.file}>{fmtDate(s.created_at, lang)} · {fmtLap(s.best_lap_s)}</div>
      </div>
    </div>
  );
}

/** Vista "Comparar sesiones": dos selectores (solo sesiones compatibles), KPIs delta y graficas. */
export default function CompareSessionsView({ seed }) {
  const { t, lang } = useLanguage();
  const [list, setList] = useState({ items: null, error: null });
  const [a, setA] = useState(seed?.a ?? '');
  const [b, setB] = useState(seed?.b ?? '');
  const [force, setForce] = useState(false);
  const [res, setRes] = useState({ key: null, data: null, error: null });

  useEffect(() => {
    let alive = true;
    listLibrary({ limit: 200 }, lang)
      .then((d) => alive && setList({ items: d.items, error: null }))
      .catch((e) => alive && setList({ items: null, error: e.code === 'network' ? t.libErrNetwork : e.message }));
    return () => { alive = false; };
  }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

  const items = useMemo(() => list.items ?? [], [list.items]);
  const sa = items.find((s) => s.id === a);
  const optionsB = useMemo(
    () => items.filter((s) => s.id !== a && (force || !sa || isCompatible(sa, s))),
    [items, a, sa, force],
  );

  const key = a && b ? `${a}|${b}|${force}|${lang}` : null;
  useEffect(() => {
    if (!key) return undefined;
    let alive = true;
    compareLibrarySessions(a, b, force, lang)
      .then((data) => alive && setRes({ key, data, error: null }))
      .catch((e) => alive && setRes({ key, data: null, error: e.code === 'network' ? t.libErrNetwork : e.message }));
    return () => { alive = false; };
    // `t` cambia con el idioma, que ya forma parte de `key`.
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const loading = !!key && res.key !== key;
  const data = key && res.key === key ? res.data : null;
  const error = key && res.key === key ? res.error : null;

  const onA = (e) => {
    const id = e.target.value;
    setA(id);
    const next = items.find((s) => s.id === id);
    const cur = items.find((s) => s.id === b);
    if (cur && next && (cur.id === id || (!force && !isCompatible(next, cur)))) setB('');
  };

  const noPairs = list.items && sa && optionsB.length === 0;

  const kpis = data && [
    { id: 'best', label: t.bestLap, fmt: fmtLap, tone: true },
    { id: 'mean', label: t.libKpiMean, fmt: fmtLap, tone: true },
    { id: 'median', label: t.libKpiMedian, fmt: fmtLap, tone: true },
    { id: 'std', label: t.libKpiStd, fmt: (v) => (v == null ? '—' : `${v.toFixed(3)} s`), tone: true },
    { id: 'laps', label: t.libColLaps, fmt: (v) => v ?? '—', digits: 0, unit: '' },
  ].map((k) => ({ ...k, ...data.kpis[k.id] }));
  const extraKpis = data && [
    { id: 'deg', label: t.degradation, v: data.degradation, digits: 3, unit: ' s/lap', fmt: (v) => (v == null ? '—' : `${v.toFixed(3)} s/lap`), tone: true },
    { id: 'fuel', label: t.libKpiFuel, v: data.fuel, digits: 2, unit: ' L', fmt: (v) => (v == null ? '—' : `${v.toFixed(2)} L`) },
  ].filter((k) => k.v.a != null && k.v.b != null);

  const toneOf = (delta, on) => (!on || delta == null || delta === 0 ? undefined : delta < 0 ? 'ok' : 'bad');

  return (
    <div className={css.view}>
      <div className={css.viewHead}>
        <div>
          <div className="ui-eyebrow">{t.libNavCompare}</div>
          <h1 className={css.h1}>{t.libCmpTitle}</h1>
          <p className={css.sub}>{t.libCmpSubtitle}</p>
        </div>
      </div>

      <Panel icon="layers" title={t.libCmpPick}>
        {list.error && <div className={css.formErr} role="alert">{list.error}</div>}
        {!list.error && !list.items && <div className={css.stateBox} role="status"><span className="shell-spin" /> {t.libLoading}</div>}
        {list.items && items.length < 2 && (
          <EmptyState icon="layers">{t.libCmpNeedTwo}</EmptyState>
        )}
        {list.items && items.length >= 2 && (
          <>
            <div className={css.pickRow}>
              <label className={css.field}>
                <span><i className={css.dot} style={{ background: LAP_COLORS[0] }} /> {t.libSessionA}</span>
                <select className={css.input} value={a} onChange={onA}>
                  <option value="">{t.libChoose}</option>
                  {items.map((s) => <option key={s.id} value={s.id}>{label(s, lang)}</option>)}
                </select>
              </label>
              <label className={css.field}>
                <span><i className={css.dot} style={{ background: LAP_COLORS[1] }} /> {t.libSessionB}</span>
                <select className={css.input} value={b} onChange={(e) => setB(e.target.value)} disabled={!a}>
                  <option value="">{a ? t.libChoose : t.libChooseAFirst}</option>
                  {optionsB.map((s) => <option key={s.id} value={s.id}>{label(s, lang)}</option>)}
                </select>
              </label>
              <label className={css.check}>
                <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
                <span>{t.libForce}</span>
              </label>
            </div>
            <p className={css.hint}>{noPairs ? t.libNoCompatible : t.libCompatHint}</p>
          </>
        )}
      </Panel>

      {loading && <div className={css.stateBox} role="status"><span className="shell-spin" /> {t.libComparing}</div>}
      {error && (
        <div className="shell-alert shell-alert--bad" role="alert"><Icon name="alert" size={16} /><div>{error}</div></div>
      )}
      {!key && list.items && items.length >= 2 && (
        <div className={css.gap}><EmptyState icon="trend">{t.libCmpPrompt}</EmptyState></div>
      )}

      {data && (
        <div className={css.results}>
          {(data.warnings?.length > 0 || data.forced) && (
            <div className="shell-alert shell-alert--warn" role="status">
              <Icon name="alert" size={16} />
              <div>{data.forced && <div>{t.libForcedWarn}</div>}{data.warnings.map((w) => <div key={w}>{w}</div>)}</div>
            </div>
          )}

          <div className="ui-grid ui-grid--2">
            <SessionCard tag="A" color={LAP_COLORS[0]} s={data.a} lang={lang} />
            <SessionCard tag="B" color={LAP_COLORS[1]} s={data.b} lang={lang} />
          </div>

          <Panel icon="file" title={t.libCmpSummary}>
            <ul className={css.summary}>
              {data.summary.map((line) => <li key={line}>{line}</li>)}
            </ul>
          </Panel>

          <Panel icon="grid" title={t.libCmpKpis} subtitle={t.libCmpSign}>
            <div className={css.kpis}>
              {[...kpis, ...extraKpis.map((k) => ({ ...k, ...k.v }))].map((k) => (
                <div key={k.id} className={css.kpi}>
                  <Stat
                    label={k.label}
                    value={k.id === 'laps' ? `${k.delta > 0 ? '+' : ''}${k.delta ?? '—'}` : fmtSigned(k.delta, k.digits ?? 3, k.unit ?? ' s')}
                    hint={`A ${k.fmt(k.a)} · B ${k.fmt(k.b)}`}
                    tone={toneOf(k.delta, k.tone)}
                  />
                </div>
              ))}
            </div>
          </Panel>

          {data.corners?.available ? (
            <Panel icon="flag" title={t.libCmpCorners} subtitle={t.libCmpCornersSub}>
              <div className={css.chart}>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={data.corners.items.map((i) => ({ ...i, name: t.libCornerShort(i.corner) }))} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid {...GRID_PROPS} />
                    <XAxis dataKey="name" tick={TICK} axisLine={AXIS_LINE} tickLine={false} />
                    <YAxis tick={TICK} axisLine={false} tickLine={false} tickFormatter={(v) => v.toFixed(2)} width={48} />
                    <ReferenceLine y={0} stroke={COLOR.ink3} />
                    <Tooltip
                      cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                      content={<ChartTooltip digits={3} unit=" s" sign hideKeys={['loss_a', 'loss_b']} nameMap={{ delta: t.libCmpDeltaB }} labelFormatter={(l) => l} />}
                    />
                    <Bar dataKey="delta" name={t.libCmpDeltaB} radius={[3, 3, 0, 0]} isAnimationActive={false}>
                      {data.corners.items.map((i) => <Cell key={i.corner} fill={i.delta < 0 ? COLOR.ok : i.delta > 0 ? COLOR.bad : COLOR.ink3} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className={css.hint}>
                {t.libCmpCornerNote}{' '}
                {data.corners.matched_by === 'apex_distance' ? t.libMatchedApex : t.libMatchedNumber}
              </p>
            </Panel>
          ) : (
            <Panel icon="flag" title={t.libCmpCorners}>
              <EmptyState icon="info">{t.libCmpNoCorners}</EmptyState>
            </Panel>
          )}

          {data.series.laps.length > 0 && (
            <Panel icon="trend" title={t.libCmpPace} subtitle={t.libCmpPaceSub}>
              <SeriesLegend items={[
                { key: 'a', color: LAP_COLORS[0], label: `A · ${data.a.title}` },
                { key: 'b', color: LAP_COLORS[1], label: `B · ${data.b.title}` },
              ]} />
              <div className={css.chart}>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={data.series.laps} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid {...GRID_PROPS} />
                    <XAxis dataKey="index" tick={TICK} axisLine={AXIS_LINE} tickLine={false} />
                    <YAxis domain={['auto', 'auto']} tick={TICK} axisLine={false} tickLine={false} tickFormatter={fmtAxisLap} width={48} />
                    <Tooltip
                      cursor={CURSOR}
                      content={<ChartTooltip labelFormatter={(l) => `${t.timelineLap} ${l}`} valueFormatter={(v) => fmtLap(v)} nameMap={{ a: 'A', b: 'B' }} />}
                    />
                    <Line type="monotone" dataKey="a" name="A" stroke={LAP_COLORS[0]} strokeWidth={2} dot={{ r: 2.5 }} activeDot={ACTIVE_DOT} isAnimationActive={false} connectNulls />
                    <Line type="monotone" dataKey="b" name="B" stroke={LAP_COLORS[1]} strokeWidth={2} dot={{ r: 2.5 }} activeDot={ACTIVE_DOT} isAnimationActive={false} connectNulls />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}
