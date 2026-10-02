import { useState, useRef, useEffect, useId } from 'react';
import { Icon } from './ui';
import { useLanguage } from '../context/LanguageContext';

export default function InfoButton({ title, content }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const popId = useId();
  const { t } = useLanguage();

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const label = title ?? t.helpLabel;

  return (
    <div ref={ref} className="info-btn">
      <button
        type="button"
        className={`info-btn__trigger${open ? ' is-open' : ''}`}
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        aria-label={label}
        title={label}
      >
        <Icon name="help" size={14} />
      </button>
      {open && (
        <div id={popId} role="dialog" aria-label={label} className="info-btn__pop">
          {title && <div className="info-btn__title">{title}</div>}
          <p>{content}</p>
        </div>
      )}
    </div>
  );
}
