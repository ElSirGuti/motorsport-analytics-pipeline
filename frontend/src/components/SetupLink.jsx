import { useId, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Badge, Icon } from './ui';
import s from './SetupLink.module.css';

const fmt = (v) => (typeof v === 'number' ? String(Math.round(v * 1000) / 1000) : String(v));
const withUnit = (v, unit) => `${fmt(v)}${unit ? (unit === '%' ? '' : ' ') + unit : ''}`;

/** Compact "PARAM  17 -> 16 psi" chips shown under the problem text. */
export function SetupChips({ link }) {
  const { t } = useLanguage();
  const primary = (link?.actions ?? []).filter((a) => !a.alternative);
  const shown = (primary.length ? primary : link?.actions ?? []).slice(0, 3);
  if (!shown.length) return null;
  return (
    <div className={s.chips}>
      {shown.map((a) => {
        if (a.status === 'at_limit') {
          return (
            <span key={a.param} className={`${s.chip} ${s.limit} ${s.mono}`}>
              <span className={s.chipLbl}>{a.label}</span>
              <span className={s.cur}>{withUnit(a.current, a.unit)}</span>
              <span className={s.warn}>{t.acsAtLimit}</span>
            </span>
          );
        }
        if (a.suggested == null) {
          return (
            <span key={a.param} className={`${s.chip} ${s.dir} ${s.mono}`}>
              <span className={s.chipLbl}>{a.label}</span>
              <span className={s.cur}>{withUnit(a.current, a.unit)}</span>
              <span className={s.arrow}>{a.direction === 'up' ? '↑' : '↓'}</span>
            </span>
          );
        }
        return (
          <span key={a.param} className={`${s.chip} ${s.mono}`}>
            <span className={s.chipLbl}>{a.label}</span>
            <span className={s.cur}>{fmt(a.current)}</span>
            <span className={s.arrow}>{'→'}</span>
            <span className={s.sug}>{withUnit(a.suggested, a.unit)}</span>
          </span>
        );
      })}
    </div>
  );
}

/** Expanded block: full current -> suggested table + related parameters. */
export function SetupDetail({ link }) {
  const { t } = useLanguage();
  if (!link) return null;
  const { actions = [], related = [] } = link;
  return (
    <div className={s.block}>
      <div className={s.blockTitle}><Icon name="wrench" size={13} />{t.acsLinkTitle}</div>
      {actions.length > 0 && (
        <table className={s.table}>
          <thead>
            <tr><th>{t.acsParam}</th><th>{t.acsCurrent}</th><th>{t.acsSuggested}</th></tr>
          </thead>
          <tbody>
            {actions.map((a) => (
              <tr key={a.param}>
                <td>
                  {a.label}
                  {a.alternative && <span className={s.alt}><Badge>{t.acsAlt}</Badge></span>}
                  {a.note && <span className={`${s.note} ${a.status === 'at_limit' ? s.warn : ''}`}>{a.note}</span>}
                </td>
                <td className={`${s.num} ${s.mono}`}>{withUnit(a.current, a.unit)}</td>
                <td className={`${s.num} ${s.mono}`}>
                  {a.status === 'at_limit' ? (
                    <Badge tone="warn">{t.acsAtLimit}</Badge>
                  ) : a.suggested != null ? (
                    <span className={s.sug}>{withUnit(a.suggested, a.unit)}</span>
                  ) : (
                    <span>{a.direction === 'up' ? t.acsDirUp : t.acsDirDown} ({t.acsDirOnly})</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {related.length > 0 && (
        <>
          <div className={s.blockTitle} style={{ marginTop: actions.length ? 12 : 0 }}>{t.acsRelated}</div>
          <table className={s.table}>
            <tbody>
              {related.map((r) => (
                <tr key={r.param}>
                  <td>{r.label}</td>
                  <td className={`${s.num} ${s.mono}`}>{withUnit(r.value, r.unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

export function ConflictBanner({ conflicts }) {
  const { t } = useLanguage();
  if (!conflicts?.length) return null;
  return (
    <div className={s.conflict} role="status">
      <Icon name="alert" size={15} />
      <div>
        <strong>{t.acsConflictTitle}.</strong>{' '}
        {t.acsConflictBody(conflicts.map((c) => c.label).join(', '))}
      </div>
    </div>
  );
}

/** "Setup used" panel: headline chips + parameters grouped by system. */
export function SetupUsedPanel({ setup, touched }) {
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  if (!setup?.params) return null;
  const date = setup.mtime ? new Date(setup.mtime * 1000).toLocaleDateString(lang) : null;
  const touchedSet = new Set(touched ?? []);
  const hasRanges = Object.values(setup.params).some((p) => p.min != null || p.max != null);
  return (
    <div>
      <div className={s.usedHead}>
        <span className={s.usedName}>{setup.name}</span>
        <span className={s.usedMeta}>{[date, t.acsParamsCount(setup.n_params)].filter(Boolean).join(' - ')}</span>
        <button type="button" className={`ui-btn ui-btn--sm ui-btn--ghost ${s.toggle}`} aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen((o) => !o)}>
          {open ? t.acsHideParams : t.acsShowParams}
          <Icon name="chevron" size={13} style={{ transform: open ? 'rotate(90deg)' : 'none' }} />
        </button>
      </div>
      {setup.summary?.length > 0 && (
        <div className={s.summary}>
          {setup.summary.map((c) => (
            <div key={c.key} className={s.sumItem}>
              <span className={s.sumLbl}>{c.label}</span>
              <span className={s.sumVal}>{c.value}</span>
            </div>
          ))}
        </div>
      )}
      {open && (
        <div id={bodyId}>
          <div className={s.groups}>
            {setup.groups.map((g) => (
              <div key={g.id} className={s.group}>
                <div className={s.groupTitle}>{g.label}</div>
                {g.items.map((k) => {
                  const p = setup.params[k];
                  return (
                    <div key={k} className={`${s.row} ${touchedSet.has(k) ? s.touched : ''}`}>
                      <span className={s.rowLbl}>{p.label}</span>
                      <span className={`${s.rowVal} ${s.mono}`}>
                        {withUnit(p.value, p.unit)}
                        {(p.min != null || p.max != null) && <span className={s.rowRange}>{p.min ?? ''} / {p.max ?? ''}</span>}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          <p className={s.foot}>{t.acsRawNote}{hasRanges ? ` ${t.acsRangeNote}` : ''}</p>
        </div>
      )}
    </div>
  );
}
