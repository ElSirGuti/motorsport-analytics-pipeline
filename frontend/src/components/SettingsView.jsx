import { useEffect, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Panel, Badge, Icon } from './ui';
import { getPaths, checkPath, savePath } from '../api/settings';
import css from './SettingsView.module.css';

const FIELDS = [
  { key: 'ac_setups_dir', icon: 'wrench', title: 'setSetupsTitle', help: 'setSetupsHelp', example: 'C:\\Users\\you\\Documents\\Assetto Corsa\\setups' },
  { key: 'ac_install_dir', icon: 'folder', title: 'setInstallTitle', help: 'setInstallHelp', example: 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa' },
];

const SOURCE_TONE = { settings: 'accent', env: undefined, auto: 'ok' };

function PathRow({ field, status, onChanged }) {
  const { t, lang } = useLanguage();
  const [value, setValue] = useState(status?.configured || '');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);       // { tone: 'ok' | 'bad', text }

  const describe = (d) => {
    if (!d) return '';
    if (field.key === 'ac_setups_dir') return t.setSetupsFound(d.n_cars ?? 0);
    return d.has_cars ? t.setInstallFound(d.n_cars ?? 0, d.n_tracks ?? 0) : t.setInstallNoContent;
  };

  const run = async (fn) => {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
    } catch (e) {
      setMsg({ tone: 'bad', text: e.message });
    } finally {
      setBusy(false);
    }
  };

  const onCheck = () => run(async () => {
    const r = await checkPath(field.key, value, lang);
    setMsg({ tone: 'ok', text: `${t.setValid} ${describe(r.details)}` });
  });
  const onSave = () => run(async () => {
    const data = await savePath(field.key, value, lang);
    onChanged(data);
    setMsg({ tone: 'ok', text: t.setSaved });
  });
  const onReset = () => run(async () => {
    const data = await savePath(field.key, '', lang);
    onChanged(data);
    setValue('');
    setMsg({ tone: 'ok', text: t.setReset });
  });

  const eff = status?.effective;
  return (
    <Panel icon={field.icon} title={t[field.title]} subtitle={t[field.help]}>
      <div className={css.row}>
        <label className={css.field}>
          <span>{t.setFolder}</span>
          <input
            className={css.input}
            value={value}
            placeholder={field.example}
            onChange={(e) => setValue(e.target.value)}
            spellCheck={false}
            autoComplete="off"
            data-testid={`path-${field.key}`}
          />
        </label>
        <div className={css.actions}>
          <button type="button" className="ui-btn ui-btn--sm" onClick={onCheck} disabled={busy || !value.trim()}>{t.setCheck}</button>
          <button type="button" className="ui-btn ui-btn--sm ui-btn--primary" onClick={onSave} disabled={busy || !value.trim()}>{t.setSave}</button>
          <button type="button" className="ui-btn ui-btn--sm" onClick={onReset} disabled={busy || !status?.configured}>{t.setUseAuto}</button>
        </div>
      </div>

      {msg && (
        <div className={`${css.msg} ${msg.tone === 'bad' ? css.bad : css.ok}`} role={msg.tone === 'bad' ? 'alert' : 'status'}>
          <Icon name={msg.tone === 'bad' ? 'alert' : 'check'} size={14} />
          <span>{msg.text}</span>
        </div>
      )}

      <div className={css.status} data-testid={`status-${field.key}`}>
        <span className={css.label}>{t.setInUse}</span>
        {eff ? <code className={css.path}>{eff}</code> : <span className={css.muted}>{t.setNotFound}</span>}
        {status?.source && <Badge tone={SOURCE_TONE[status.source]}>{t[`setSource_${status.source}`]}</Badge>}
        {eff && <Badge tone={status.exists ? 'ok' : 'warn'}>{status.exists ? t.setExists : t.setMissing}</Badge>}
        {status?.exists && <span className={css.muted}>{describe(status.details)}</span>}
      </div>
      {status?.source === 'env' && <p className={css.note}>{t.setEnvNote}</p>}
    </Panel>
  );
}

export default function SettingsView() {
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    getPaths()
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, []);

  return (
    <div className={css.root}>
      <div>
        <h2 className={css.h}>{t.setTitle}</h2>
        <p className={css.lead}>{t.setLead}</p>
      </div>
      {error && <div className={`${css.msg} ${css.bad}`} role="alert"><Icon name="alert" size={14} /><span>{error}</span></div>}
      {FIELDS.map((f) => (
        <PathRow key={`${f.key}:${data ? 'ready' : 'loading'}`} field={f} status={data?.paths?.[f.key]} onChanged={setData} />
      ))}
      <p className={css.note}>{t.setDockerNote}</p>
      {data?.settings_file && <p className={css.note}>{t.setStoredIn}: <code>{data.settings_file}</code></p>}
    </div>
  );
}
