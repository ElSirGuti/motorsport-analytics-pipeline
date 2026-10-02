import { useLanguage } from '../context/LanguageContext';
import { Badge } from './ui';
import { detectFormat } from '../utils/formats';

/** Shows the detected telemetry format and an "Experimental" badge for native binary formats. */
export default function FormatBadge({ file }) {
  const { t } = useLanguage();
  const fmt = detectFormat(file?.name);
  if (!fmt || !fmt.experimental) return null;
  return (
    <>
      <Badge title={t.fmtDetected.replace('{format}', fmt.label)}>{fmt.label}</Badge>
      <Badge tone="warn" title={t.fmtExperimentalHint}>{t.fmtExperimental}</Badge>
    </>
  );
}
