// Shared chart primitives (colours, axes, tooltip) so every chart looks the same.
import { useLanguage } from '../context/LanguageContext';
import { Badge, Panel, EmptyState } from './ui';
import styles from './chartKit.module.css';

/**
 * Sober tooltip. Props: unit (string), digits, nameMap, sign (bool), labelFormatter, valueFormatter.
 * Used as <Tooltip content={<ChartTooltip ... />} cursor={CURSOR} />
 */
export function ChartTooltip({
  active, payload, label, unit = '', digits = 1, nameMap = {}, sign = false,
  labelFormatter, valueFormatter, hideKeys = [],
}) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p) => p.value != null && !hideKeys.includes(p.dataKey) && !p.hide);
  if (!rows.length) return null;
  return (
    <div className={styles.tip}>
      <div className={styles.tipHead}>{labelFormatter ? labelFormatter(label) : `${Number(label).toFixed(0)} m`}</div>
      {rows.map((p) => {
        const v = Number(p.value);
        const text = valueFormatter ? valueFormatter(v, p) : `${sign && v > 0 ? '+' : ''}${v.toFixed(digits)}${unit}`;
        return (
          <div key={p.dataKey ?? p.name} className={styles.tipRow}>
            <span className={styles.swatch} style={{ background: p.stroke && p.stroke !== 'none' ? p.stroke : p.color }} />
            <span className={styles.tipName}>{nameMap[p.dataKey] || nameMap[p.name] || p.name}</span>
            <span className={styles.tipVal}>{text}</span>
          </div>
        );
      })}
    </div>
  );
}

export function ZoomBadge({ domain }) {
  const { t } = useLanguage();
  if (!domain) return null;
  return <Badge tone="accent">{t.zoomBadge} {domain[0].toFixed(0)}–{domain[1].toFixed(0)} m</Badge>;
}

/** Legend rendered as HTML (above the plot) rather than Recharts' Legend. */
export function SeriesLegend({ items }) {
  return (
    <ul className={styles.legend}>
      {items.map((it) => (
        <li key={it.key} className={styles.legendItem}>
          <span className={styles.legendLine} style={{ background: it.color }} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

export function ChartEmpty({ icon, title, children }) {
  return (
    <Panel icon={icon} title={title}>
      <EmptyState icon="activity">{children}</EmptyState>
    </Panel>
  );
}
