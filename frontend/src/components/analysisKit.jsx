/* eslint-disable react-refresh/only-export-components -- shared chart constants and helpers */
import styles from './Analysis.module.css';

export const COLOR_A = 'var(--lap-a)';
export const COLOR_B = 'var(--lap-b)';
export const COLOR_C = 'var(--lap-c)';
export const COLOR_D = 'var(--lap-d)';
export const COLOR_E = 'var(--lap-e)';
export const COLOR_F = 'var(--lap-f)';

export const AXIS_TICK = { fontSize: 11, fill: 'var(--ink-3)' };
export const AXIS_LINE = { stroke: 'var(--line-strong)' };
export const GRID_PROPS = { stroke: 'var(--line)', strokeDasharray: '3 3', vertical: false };
export const REF_ZERO = 'var(--ink-4)';
export const CHART_MARGIN = { top: 6, right: 12, bottom: 0, left: 0 };
export const fmtDist = (v) => `${Number(v).toFixed(0)} m`;

/** Strip decorative glyphs (check, warning...) that older i18n strings carry. */
export const cleanLabel = (s) => (typeof s === 'string' ? s.replace(/^[^A-Za-z0-9À-ɏ]+/, '') : s);

/** Sober tooltip factory. fmt(value, entry) returns a string. */
export const makeTooltip = (fmt) => function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={styles.tip}>
      <div className={styles.tipHead}>{Number(label).toFixed(0)} m</div>
      {payload.map((p) => {
        if (p.value == null) return null;
        return (
          <div key={p.dataKey} className={styles.tipRow}>
            <span className={styles.swatch} style={{ background: p.color || p.stroke }} />
            <span>{p.name}</span>
            <span className={styles.tipVal}>{fmt(p.value, p)}</span>
          </div>
        );
      })}
    </div>
  );
};

/** items: [{label, color, dashed}] */
export const Legend = ({ items }) => (
  <div className={styles.legend}>
    {items.map((it) => (
      <span key={it.label} className={styles.legendItem}>
        <span className={`${styles.legendLine} ${it.dashed ? styles.legendDash : ''}`} style={{ borderColor: it.color }} />
        {it.label}
      </span>
    ))}
  </div>
);
