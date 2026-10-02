import { useCallback, useEffect, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { annotateRecommendations } from '../api/setups';
import SetupSelector from './SetupSelector';
import SetupRecommendations from './SetupRecommendations';

/**
 * Setup advisor + Assetto Corsa setup linking.
 * `file` is the telemetry CSV of the session (its header tells car and track).
 * Without a file the advisor renders exactly as before.
 */
export default function SetupSection({ file, setup_advisor, source, isPilotMode }) {
  const { lang } = useLanguage();
  const [sel, setSel] = useState({ file: null, setup: null });
  const [annot, setAnnot] = useState(null);

  const handleSelect = useCallback((setup) => setSel({ file, setup }), [file]);
  const setup = sel.file === file ? sel.setup : null;
  const recs = setup_advisor?.recommendations;

  useEffect(() => {
    if (!setup || !recs?.length) return undefined;
    let alive = true;
    annotateRecommendations(setup, recs, lang)
      .then((data) => { if (alive) setAnnot({ setup, recs, data }); })
      .catch(() => { if (alive) setAnnot(null); });
    return () => { alive = false; };
  }, [setup, recs, lang]);

  const annotated = setup && annot && annot.setup === setup && annot.recs === recs ? annot.data : null;

  return (
    <div>
      {file && (
        <div style={{ marginBottom: 12 }}>
          <SetupSelector file={file} onChange={handleSelect} />
        </div>
      )}
      <SetupRecommendations
        setup_advisor={setup_advisor}
        source={source}
        isPilotMode={isPilotMode}
        setup={setup}
        annotated={annotated}
      />
    </div>
  );
}
