import { useLanguage } from '../context/LanguageContext';
import { Badge, Icon } from './ui';
import { countryName } from '../utils/cornerLabel';

const fmt = (s, vars) => String(s ?? '').replace(/\{(\w+)\}/g, (_, k) => (vars?.[k] ?? `{${k}}`));

/**
 * Discreet badge with the recognised circuit (and country). Neutral "not recognized" when the
 * venue is unknown; amber when the venue is known but the measured lap length does not fit.
 * `circuit` is the additive `circuit` object of the API responses.
 */
export default function CircuitBadge({ circuit }) {
  const { t, lang } = useLanguage();
  if (!circuit || typeof circuit !== 'object') return null;

  if (!circuit.recognized) {
    return (
      <span style={{ display: 'inline-flex', minWidth: 0 }} title={t.circuitUnknownHint}>
        <Badge>{t.circuitUnknown}</Badge>
      </span>
    );
  }

  const country = countryName(circuit.country, lang);
  const label = [circuit.short_name || circuit.name, country].filter(Boolean).join(' · ');
  const km = (circuit.length_m / 1000).toFixed(3);

  if (!circuit.matched) {
    const dev = circuit.length_deviation_pct;
    const title = fmt(t.circuitLowConfidenceHint, {
      name: circuit.name,
      measured: Math.round(circuit.measured_length_m ?? 0),
      nominal: Math.round(circuit.length_m ?? 0),
      dev: dev != null ? `${dev > 0 ? '+' : ''}${dev.toFixed(1)}` : '?',
    });
    return (
      <span style={{ display: 'inline-flex', minWidth: 0 }} title={title}>
        <Badge tone="warn"><Icon name="flag" size={12} /> {label} · {t.circuitLowConfidence}</Badge>
      </span>
    );
  }

  const confidence = circuit.confidence === 'high' ? t.circuitConfidenceHigh : t.circuitConfidenceMedium;
  const title = fmt(circuit.named_corners > 0 ? t.circuitMatchedHint : t.circuitMatchedNoCorners,
    { name: circuit.name, length: km, named: circuit.named_corners, confidence });
  return (
    <span style={{ display: 'inline-flex', minWidth: 0 }} title={title}>
      <Badge><Icon name="flag" size={12} /> {label}</Badge>
    </span>
  );
}
