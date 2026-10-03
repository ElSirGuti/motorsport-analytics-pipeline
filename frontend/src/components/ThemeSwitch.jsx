import { useLanguage } from '../context/LanguageContext';
import useTheme from '../hooks/useTheme';
import { Icon } from './ui';

const OPTIONS = [
  { value: 'system', icon: 'monitor', label: 'themeSystem' },
  { value: 'light', icon: 'sun', label: 'themeLight' },
  { value: 'dark', icon: 'moon', label: 'themeDark' },
];

/** Segmented System | Light | Dark selector for the app bar. */
export default function ThemeSwitch() {
  const { t } = useLanguage();
  const { pref, setPref } = useTheme();
  return (
    <div className="ui-seg ui-seg--icons" role="group" aria-label={t.themeLabel} title={t.themeLabel}>
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          className="ui-seg__item"
          aria-pressed={pref === o.value}
          aria-label={t[o.label]}
          title={o.value === 'system' ? `${t.themeSystem} - ${t.themeSystemHint}` : t[o.label]}
          onClick={() => setPref(o.value)}
        >
          <Icon name={o.icon} size={15} />
        </button>
      ))}
    </div>
  );
}
