import { useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { cornerLabel } from '../utils/cornerLabel';
import { isNoPhase } from '../utils/cornerKind';
import { kindTip } from '../utils/cornerTips';

const R = 7.5;
const R2 = 9.5; // two-digit numbers need a wider circle to stay legible
const radiusOf = (n) => (n > 9 ? R2 : R);

/**
 * Numbered corner circles for an SVG track map. `items`: [{x, y, number, name, kind}] in viewBox
 * units. The corner name shows on hover / focus (and as a native tooltip). `width` is the viewBox
 * width, used to flip the label away from the right edge.
 */
export default function CornerMarkers({ items, width = 600 }) {
  const { t } = useLanguage();
  const [hover, setHover] = useState(null);
  if (!items?.length) return null;
  const active = hover != null ? items.find((i) => i.number === hover) : null;
  return (
    <g data-testid="corner-markers">
      {items.map((it) => {
        const flat = isNoPhase(it);
        const tip = [cornerLabel(t, it.number, it.name), kindTip(t, it)].filter(Boolean).join('\n');
        return (
          <g
            key={it.number}
            tabIndex={0}
            role="img"
            aria-label={cornerLabel(t, it.number, it.name)}
            onMouseEnter={() => setHover(it.number)}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(it.number)}
            onBlur={() => setHover(null)}
            style={{ cursor: 'default', outline: 'none' }}
          >
            <title>{tip}</title>
            <circle
              cx={it.x} cy={it.y} r={radiusOf(it.number)}
              fill="var(--map-halo)" stroke={hover === it.number ? 'var(--accent)' : 'var(--ink-2)'} strokeWidth="1.25"
              strokeDasharray={flat ? '2.5 2' : undefined}
            />
            <text
              x={it.x} y={it.y} dy="3.2" textAnchor="middle"
              fontSize={it.number > 9 ? 8.5 : 9} fontWeight="700" letterSpacing={it.number > 9 ? '0.3' : undefined} fill="var(--ink-1)"
              fontFamily="JetBrains Mono, monospace" style={{ pointerEvents: 'none' }}
            >
              {it.number}
            </text>
          </g>
        );
      })}
      {active && (
        <text
          x={active.x + (active.x > width * 0.75 ? -(R2 + 4) : R2 + 4)} y={active.y} dy="3.5"
          textAnchor={active.x > width * 0.75 ? 'end' : 'start'}
          fontSize="11" fontWeight="600" fill="var(--ink-1)"
          stroke="var(--map-halo)" strokeWidth="3" paintOrder="stroke"
          fontFamily="JetBrains Mono, monospace" style={{ pointerEvents: 'none' }}
        >
          {cornerLabel(t, active.number, active.name)}
        </text>
      )}
    </g>
  );
}
