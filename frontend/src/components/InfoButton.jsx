import { useState, useRef, useEffect } from 'react';

export default function InfoButton({ title, content }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: 18, height: 18, borderRadius: '50%',
          background: open ? 'rgba(0,212,255,0.15)' : 'rgba(255,255,255,0.06)',
          border: `1px solid ${open ? 'rgba(0,212,255,0.4)' : 'rgba(255,255,255,0.12)'}`,
          color: open ? '#00D4FF' : '#7080A0',
          fontSize: 11, fontWeight: 700, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 0, lineHeight: 1, flexShrink: 0,
          transition: 'all 0.15s',
        }}
      >
        ?
      </button>
      {open && (
        <div style={{
          position: 'absolute', bottom: 24, right: 0, zIndex: 200,
          background: 'rgba(8,12,24,0.98)',
          border: '1px solid rgba(0,212,255,0.2)',
          borderRadius: 8, padding: '12px 14px',
          width: 300, maxWidth: '90vw',
          fontSize: 11, color: '#9AAABB', lineHeight: 1.65,
          boxShadow: '0 8px 32px rgba(0,0,0,0.7)',
          whiteSpace: 'pre-line',
        }}>
          {title && (
            <div style={{ color: '#00D4FF', fontWeight: 700, fontSize: 12, marginBottom: 8 }}>
              {title}
            </div>
          )}
          <p style={{ margin: 0 }}>{content}</p>
        </div>
      )}
    </div>
  );
}
