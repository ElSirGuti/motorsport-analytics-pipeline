import { useState, useEffect, useRef } from 'react';

const COMPARE_SECTIONS = [
  { id: 'section-core-lap',  icon: '⏱', label: 'Core Lap' },
  { id: 'section-dynamics',  icon: '◎', label: 'Vehicle Dynamics' },
  { id: 'section-inputs',    icon: '🎮', label: 'Driver & Inputs' },
  { id: 'section-strategy',  icon: '🏁', label: 'Strategy & Setup' },
];

const SESSION_SECTIONS = [
  { id: 'section-overview', icon: '▦', label: 'Overview' },
  { id: 'section-stint',    icon: '◎', label: 'Stint Analysis' },
  { id: 'section-setup',    icon: '🔧', label: 'Setup & Strategy' },
];

const PILOT_HIDDEN = new Set(['section-dynamics', 'section-inputs']);

export default function Sidebar({ mode, isPilotMode, resultKey }) {
  const SEP = { id: '__sep__', separator: true };
  const visibleCompare = isPilotMode
    ? COMPARE_SECTIONS.filter(s => !PILOT_HIDDEN.has(s.id))
    : COMPARE_SECTIONS;
  const sections =
    mode === 'session' ? SESSION_SECTIONS :
    mode === 'both'    ? [...SESSION_SECTIONS, SEP, ...visibleCompare] :
    visibleCompare;

  const [activeId, setActiveId] = useState(null);
  const scrollLockRef = useRef(false);
  const scrollLockTimerRef = useRef(null);

  useEffect(() => {
    let observers = [];
    let rafId;

    const setup = () => {
      observers.forEach(o => o.disconnect());
      observers = [];
      sections.forEach(({ id }) => {
        const el = document.getElementById(id);
        if (!el) return;
        const obs = new IntersectionObserver(
          ([entry]) => {
            if (!scrollLockRef.current && entry.isIntersecting) setActiveId(id);
          },
          { threshold: 0.15, rootMargin: '-60px 0px -60% 0px' }
        );
        obs.observe(el);
        observers.push(obs);
      });
    };

    // defer one frame so DOM is committed before observing
    rafId = requestAnimationFrame(setup);
    return () => {
      cancelAnimationFrame(rafId);
      observers.forEach(o => o.disconnect());
    };
  }, [mode, resultKey, isPilotMode]);

  // cleanup timer on unmount
  useEffect(() => () => clearTimeout(scrollLockTimerRef.current), []);

  const scrollTo = (id) => {
    setActiveId(id);
    // prevent the IntersectionObserver from overriding during smooth scroll
    scrollLockRef.current = true;
    clearTimeout(scrollLockTimerRef.current);
    scrollLockTimerRef.current = setTimeout(() => {
      scrollLockRef.current = false;
    }, 800);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <aside style={{
      width: 200,
      flexShrink: 0,
      position: 'sticky',
      top: 64,
      height: 'calc(100vh - 80px)',
      overflowY: 'auto',
      paddingTop: 'var(--s4)',
      paddingRight: 'var(--s3)',
      paddingLeft: 4,
    }}>
      <div style={{
        fontSize: '0.6rem',
        fontWeight: 700,
        letterSpacing: '0.12em',
        color: 'var(--text-3)',
        textTransform: 'uppercase',
        marginBottom: 'var(--s3)',
        paddingLeft: 12,
      }}>
        Analysis
      </div>
      {sections.map(({ id, icon, label, separator }) => {
        if (separator) {
          return (
            <div key="sep" style={{
              height: 1,
              background: 'var(--border-1)',
              margin: '8px 12px 10px',
            }} />
          );
        }
        const isActive = activeId === id;
        return (
          <button
            key={id}
            onClick={() => scrollTo(id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              width: '100%',
              background: isActive ? 'rgba(0,212,255,0.08)' : 'transparent',
              border: 'none',
              borderLeft: `2px solid ${isActive ? 'var(--cyan)' : 'transparent'}`,
              borderRadius: '0 6px 6px 0',
              color: isActive ? 'var(--cyan)' : 'var(--text-2)',
              cursor: 'pointer',
              fontSize: '0.75rem',
              fontWeight: isActive ? 600 : 400,
              padding: '8px 10px 8px 12px',
              textAlign: 'left',
              transition: 'all 0.15s',
              marginBottom: 2,
            }}
          >
            <span style={{ fontSize: '0.85rem', opacity: isActive ? 1 : 0.6 }}>{icon}</span>
            {label}
          </button>
        );
      })}
    </aside>
  );
}
