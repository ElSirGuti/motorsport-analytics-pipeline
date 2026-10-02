import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import styles from './SectorTable.module.css';

const sign = (v) => (v > 0 ? '+' : '');

const SectorTable = ({ sectores, totalDelta }) => {
  const { t } = useLanguage();
  if (!sectores || sectores.length === 0) return null;

  const maxAbs = Math.max(...sectores.map((s) => Math.abs(s.delta_parcial)));

  return (
    <Panel
      icon="layers"
      title={t.sectorTitle}
      flush
      actions={totalDelta != null && (
        <Badge tone={totalDelta > 0 ? 'bad' : 'ok'}>
          Total {sign(totalDelta)}{totalDelta.toFixed(3)} s
        </Badge>
      )}
    >
      <div className={styles.scroll}>
        <table className="ui-table">
          <thead>
            <tr>
              <th>{t.sectorNumber}</th>
              <th>{t.sectorZone}</th>
              <th className="is-num">{t.sectorMeters}</th>
              <th className="is-num">{t.sectorPartialDelta}</th>
              <th className={styles.barCol}>{t.sectorBar}</th>
            </tr>
          </thead>
          <tbody>
            {sectores.map((s) => {
              const isLoss = s.delta_parcial > 0.01;
              const isGain = s.delta_parcial < -0.01;
              const pct = maxAbs > 0 ? Math.abs(s.delta_parcial) / maxAbs : 0;
              const color = isLoss ? 'var(--bad)' : isGain ? 'var(--ok)' : 'var(--ink-4)';
              const longitud = (s.dist_fin - s.dist_inicio).toFixed(0);
              return (
                <tr key={s.sector}>
                  <td className={styles.num}>{s.sector}</td>
                  <td className={styles.zone}>{s.descripcion}</td>
                  <td className="is-num">{longitud} m</td>
                  <td className="is-num" style={{ color, fontWeight: 600 }}>
                    {sign(s.delta_parcial)}{s.delta_parcial.toFixed(3)} s
                  </td>
                  <td className={styles.barCol}>
                    <div className={styles.track}>
                      <div className={styles.fill} style={{ width: `${(pct * 100).toFixed(1)}%`, background: color }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
};

export default SectorTable;
