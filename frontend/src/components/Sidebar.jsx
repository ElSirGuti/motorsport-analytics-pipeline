import { useState, useEffect, useRef } from 'react';
import { Icon } from './ui';
import { useLanguage } from '../context/LanguageContext';
import { SESSION_SECTIONS, COMPARE_SECTIONS, PILOT_HIDDEN, sectionLabel } from './navSections';

export default function Sidebar({ mode, isPilotMode, resultKey }) {
  const { t } = useLanguage();
  const visibleCompare = isPilotMode
    ? COMPARE_SECTIONS.filter(s => !PILOT_HIDDEN.has(s.id))
    : COMPARE_SECTIONS;

  const groups = [];
  if (mode === 'session' || mode === 'both') {
    groups.push({
      key: 'session',
      title: t.navSession,
      items: SESSION_SECTIONS,
    });
  }
  if (mode === 'compare' || mode === 'both') {
    groups.push({
      key: 'compare',
      title: t.navComparison,
      items: visibleCompare,
    });
  }
  const sections = groups.flatMap(g => g.items);

  const [activeId, setActiveId] = useState(null);
  const scrollLockRef = useRef(false);
  const scrollLockTimerRef = useRef(null);
  const idsKey = sections.map(s => s.id).join('|');

  useEffect(() => {
    let observers = [];
    const ids = idsKey ? idsKey.split('|') : [];

    const setup = () => {
      observers.forEach(o => o.disconnect());
      observers = [];
      ids.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        const obs = new IntersectionObserver(
          ([entry]) => {
            if (!scrollLockRef.current && entry.isIntersecting) setActiveId(id);
          },
          { threshold: 0.05, rootMargin: '-72px 0px -60% 0px' }
        );
        obs.observe(el);
        observers.push(obs);
      });
    };

    // defer one frame so the DOM is committed before observing
    const rafId = requestAnimationFrame(setup);
    return () => {
      cancelAnimationFrame(rafId);
      observers.forEach(o => o.disconnect());
    };
  }, [mode, resultKey, isPilotMode, idsKey]);

  useEffect(() => () => clearTimeout(scrollLockTimerRef.current), []);

  const scrollTo = (id) => {
    setActiveId(id);
    // keep the observer from overriding the choice during the smooth scroll
    scrollLockRef.current = true;
    clearTimeout(scrollLockTimerRef.current);
    scrollLockTimerRef.current = setTimeout(() => { scrollLockRef.current = false; }, 800);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <nav className="shell-rail" aria-label={t.navAria}>
      {groups.map(g => (
        <div className="shell-rail__group" key={g.key}>
          <div className="shell-rail__title">{g.title}</div>
          {g.items.map(({ id, icon }) => {
            const isActive = activeId === id;
            return (
              <button
                key={id}
                type="button"
                className={`shell-rail__item${isActive ? ' is-active' : ''}`}
                aria-current={isActive ? 'location' : undefined}
                onClick={() => scrollTo(id)}
              >
                <Icon name={icon} size={16} />
                <span>{sectionLabel(id, t)}</span>
              </button>
            );
          })}
        </div>
      ))}
      {isPilotMode && (
        <div className="shell-rail__note">
          <Icon name="info" size={14} />
          <span>{t.navPilotNote}</span>
        </div>
      )}
    </nav>
  );
}
