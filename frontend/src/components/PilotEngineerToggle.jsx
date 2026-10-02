import { useLanguage } from '../context/LanguageContext';

export default function PilotEngineerToggle({ isPilotMode, onToggle }) {
  const { t, lang } = useLanguage();
  const es = lang === 'es';
  const engineerLabel = t.viewEngineer ?? (es ? 'Ingeniero' : 'Engineer');
  const pilotLabel = t.viewPilot ?? (es ? 'Piloto' : 'Pilot');
  const hint = isPilotMode
    ? (t.viewPilotHint ?? (es ? 'Modo piloto: paneles técnicos ocultos' : 'Pilot mode: technical panels hidden'))
    : (t.viewEngineerHint ?? (es ? 'Modo ingeniero: telemetría completa' : 'Engineer mode: full telemetry'));

  return (
    <div
      className="ui-seg"
      role="group"
      aria-label={t.viewModeAria ?? (es ? 'Modo de vista' : 'View mode')}
      title={hint}
    >
      <button
        type="button"
        className="ui-seg__item"
        aria-pressed={!isPilotMode}
        onClick={isPilotMode ? onToggle : undefined}
      >
        {engineerLabel}
      </button>
      <button
        type="button"
        className="ui-seg__item"
        aria-pressed={isPilotMode}
        onClick={isPilotMode ? undefined : onToggle}
      >
        {pilotLabel}
      </button>
    </div>
  );
}
