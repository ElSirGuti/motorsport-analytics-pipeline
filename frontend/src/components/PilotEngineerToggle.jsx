import { useLanguage } from '../context/LanguageContext';

export default function PilotEngineerToggle({ isPilotMode, onToggle }) {
  const { t } = useLanguage();
  const engineerLabel = t.viewEngineer;
  const pilotLabel = t.viewPilot;
  const hint = isPilotMode ? t.viewPilotHint : t.viewEngineerHint;

  return (
    <div
      className="ui-seg"
      role="group"
      aria-label={t.viewModeAria}
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
