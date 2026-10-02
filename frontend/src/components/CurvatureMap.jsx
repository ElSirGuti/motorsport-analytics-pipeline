import { useMemo } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge } from './ui';
import { COLOR } from './chartTheme';

const MONO = 'JetBrains Mono, monospace';

const CurvatureMap = ({ curvatura, apexes }) => {
  const { t } = useLanguage();
  const { path, apexPoints, viewBox } = useMemo(() => {
    if (!curvatura || curvatura.length < 2) return { path: '', apexPoints: [], viewBox: '0 0 100 40' };

    const W = 800;
    const H = 120;

    const dists = curvatura.map((r) => r.Distance);
    const kappas = curvatura.map((r) => r.Curvature);
    const maxD = Math.max(...dists);
    const maxK = Math.max(...kappas) || 1;

    const pts = curvatura.map((r, i) => {
      const x = (r.Distance / maxD) * W;
      const y = H - (r.Curvature / maxK) * (H * 0.85) - H * 0.05;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const apexPts = (apexes || []).map((a, i) => ({
      x: ((a.Distance || 0) / maxD) * W,
      y: H - ((a.Curvature || 0) / maxK) * (H * 0.85) - H * 0.05,
      num: i + 1,
      speed: a.Speed,
      dist: a.Distance,
    }));

    return {
      path: pts.join(' '),
      apexPoints: apexPts,
      viewBox: `0 0 ${W} ${H + 30}`,
    };
  }, [curvatura, apexes]);

  if (!path) return null;

  return (
    <Panel
      icon="activity"
      title={t.curvatureTitle}
      actions={<Badge>{t.curvatureCorners(apexes?.length || 0)}</Badge>}
    >
      <svg
        viewBox={viewBox}
        role="img"
        style={{ width: '100%', height: 160, overflow: 'visible' }}
        aria-label={t.curvatureAria}
      >
        <line x1="0" y1="120" x2="800" y2="120" stroke={COLOR.lineStrong} strokeWidth="1" />

        <path d={`${path} L800,120 L0,120 Z`} fill={COLOR.accent} fillOpacity={0.1} />
        <path d={path} fill="none" stroke={COLOR.accent} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />

        {apexPoints.map((a) => (
          <g key={a.num}>
            <line x1={a.x} y1={a.y + 4} x2={a.x} y2={120} stroke={COLOR.warn} strokeWidth="1" strokeDasharray="3 2" strokeOpacity={0.5} />
            <circle cx={a.x} cy={a.y} r={4} fill={COLOR.warn} stroke="#12161c" strokeWidth={1.5} />
            <text x={a.x} y={a.y - 10} textAnchor="middle" fontSize="10" fill={COLOR.warn} fontFamily={MONO} fontWeight="600">
              {a.num}
            </text>
            <text x={a.x} y={135} textAnchor="middle" fontSize="9" fill={COLOR.ink3} fontFamily={MONO}>
              {a.dist?.toFixed(0)}
            </text>
          </g>
        ))}
        <text x="800" y="149" textAnchor="end" fontSize="9" fill={COLOR.ink3} fontFamily={MONO}>m</text>
      </svg>
    </Panel>
  );
};

export default CurvatureMap;
