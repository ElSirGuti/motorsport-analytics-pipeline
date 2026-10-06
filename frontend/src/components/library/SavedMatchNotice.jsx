import { useState } from 'react';
import { useLanguage } from '../../context/LanguageContext';
import { getLibrarySession } from '../../api/library';
import { Icon } from '../ui';
import css from './Library.module.css';

/** "You already analysed this session" with a shortcut to open the saved result. */
export default function SavedMatchNotice({ items, onOpen, afterAnalysis = false, busy = false }) {
  const { t, lang } = useLanguage();
  const [opening, setOpening] = useState(false);
  const [err, setErr] = useState('');
  if (!items?.length) return null;
  const it = items[0];
  const date = it.updated_at || it.created_at;
  const when = date ? new Date(date).toLocaleDateString(lang, { dateStyle: 'medium' }) : '';

  const open = async () => {
    setOpening(true);
    setErr('');
    try {
      onOpen(await getLibrarySession(it.id, lang));
    } catch (e) {
      setErr(e.message);
    } finally {
      setOpening(false);
    }
  };

  return (
    <div className={css.savedMatch} role="status" data-testid="saved-match">
      <Icon name="info" size={15} />
      <span className={css.savedMatchText}>
        <strong>{t.libDupTitle}</strong>{' '}
        {t.libDupBody(it.title, when, it.n_laps)}{' '}
        {afterAnalysis ? t.libDupAfter : t.libDupBefore}
      </span>
      {!afterAnalysis && (
        <button type="button" className="ui-btn ui-btn--sm" onClick={open} disabled={opening || busy} data-testid="saved-match-open">
          {t.libDupOpen}
        </button>
      )}
      {err && <span className={css.savedMatchErr} role="alert">{err}</span>}
    </div>
  );
}
