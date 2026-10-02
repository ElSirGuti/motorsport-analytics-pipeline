import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLanguage } from '../../context/LanguageContext';
import { Badge, EmptyState, Icon, Panel } from '../ui';
import {
  deleteLibrarySession, getLibrarySession, libraryFacets, listLibrary, patchLibrarySession,
} from '../../api/library';
import { fmtDate, fmtLap, isCompatible } from './libUtil';
import css from './Library.module.css';

const PAGE = 20;

/** Vista "Biblioteca": sesiones guardadas con filtros, renombrar, borrar, abrir y comparar. */
export default function LibraryView({ onOpen, onCompare, openedId }) {
  const { t, lang } = useLanguage();
  const [filters, setFilters] = useState({ q: '', venue: '', vehicle: '', from: '', to: '' });
  const [debouncedQ, setDebouncedQ] = useState('');
  const [page, setPage] = useState(0);
  const [reload, setReload] = useState(0);
  const [res, setRes] = useState({ key: null, data: null, error: null });
  const [facets, setFacets] = useState(null);
  const [editing, setEditing] = useState(null);      // {id, value}
  const [confirmId, setConfirmId] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [rowError, setRowError] = useState(null);
  const [selected, setSelected] = useState([]);

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(filters.q), 300);
    return () => clearTimeout(id);
  }, [filters.q]);

  const params = useMemo(() => {
    const p = { limit: PAGE, offset: page * PAGE };
    if (debouncedQ.trim()) p.q = debouncedQ.trim();
    if (filters.venue) p.venue = filters.venue;
    if (filters.vehicle) p.vehicle = filters.vehicle;
    if (filters.from) p.date_from = filters.from;
    if (filters.to) p.date_to = filters.to;
    return p;
  }, [debouncedQ, filters.venue, filters.vehicle, filters.from, filters.to, page]);
  const key = `${JSON.stringify(params)}#${reload}#${lang}`;

  useEffect(() => {
    let alive = true;
    listLibrary(params, lang)
      .then((data) => alive && setRes({ key, data, error: null }))
      .catch((e) => alive && setRes({ key, data: null, error: e.code === 'network' ? t.libErrNetwork : e.message }));
    return () => { alive = false; };
    // `t` cambia con el idioma, igual que `lang` (ya en `key`).
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let alive = true;
    libraryFacets().then((f) => alive && setFacets(f)).catch(() => {});
    return () => { alive = false; };
  }, [reload]);

  const loading = res.key !== key;
  const items = res.data?.items ?? [];
  const total = res.data?.total ?? 0;
  const filtered = !!(debouncedQ || filters.venue || filters.vehicle || filters.from || filters.to);
  const pages = Math.max(1, Math.ceil(total / PAGE));

  const setFilter = (k) => (e) => { setFilters((f) => ({ ...f, [k]: e.target.value })); setPage(0); };
  const clearFilters = () => { setFilters({ q: '', venue: '', vehicle: '', from: '', to: '' }); setPage(0); };
  const refresh = useCallback(() => setReload((n) => n + 1), []);
  const fail = (e) => setRowError(e.code === 'network' ? t.libErrNetwork : e.message);

  const open = async (row) => {
    setBusyId(row.id); setRowError(null);
    try {
      onOpen(await getLibrarySession(row.id, lang));
    } catch (e) { fail(e); } finally { setBusyId(null); }
  };

  const commitRename = async () => {
    if (!editing) return;
    const { id, value } = editing;
    const title = value.trim();
    setEditing(null);
    if (!title) return;
    setBusyId(id); setRowError(null);
    try {
      await patchLibrarySession(id, { title }, lang);
      refresh();
    } catch (e) { fail(e); } finally { setBusyId(null); }
  };

  const remove = async (row) => {
    setConfirmId(null); setBusyId(row.id); setRowError(null);
    try {
      await deleteLibrarySession(row.id, lang);
      setSelected((s) => s.filter((x) => x !== row.id));
      if (items.length === 1 && page > 0) setPage(page - 1);
      refresh();
    } catch (e) { fail(e); } finally { setBusyId(null); }
  };

  const toggleSel = (row) => setSelected((s) => (
    s.includes(row.id) ? s.filter((x) => x !== row.id) : [...s, row.id].slice(-2)
  ));
  const selRows = selected.map((id) => items.find((r) => r.id === id)).filter(Boolean);
  const canCompare = selected.length === 2 && selRows.length === 2 && isCompatible(selRows[0], selRows[1]);

  return (
    <div className={css.view}>
      <div className={css.viewHead}>
        <div>
          <div className="ui-eyebrow">{t.libNavLibrary}</div>
          <h1 className={css.h1}>{t.libTitle}</h1>
          <p className={css.sub}>{t.libSubtitle}</p>
        </div>
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          disabled={selected.length !== 2 || (selRows.length === 2 && !canCompare)}
          onClick={() => onCompare(selected[0], selected[1])}
          title={selRows.length === 2 && !canCompare ? t.libCompareIncompatible : t.libCompareSelectedHint}
        >
          <Icon name="trend" size={14} /> {t.libCompareSelected(selected.length)}
        </button>
      </div>

      <Panel flush>
        <div className={css.filters}>
          <label className={`${css.field} ${css.grow}`}>
            <span>{t.libSearch}</span>
            <input className={css.input} type="search" value={filters.q} onChange={setFilter('q')} placeholder={t.libSearchPh} />
          </label>
          <label className={css.field}>
            <span>{t.libFieldVenue}</span>
            <select className={css.input} value={filters.venue} onChange={setFilter('venue')}>
              <option value="">{t.libAll}</option>
              {facets?.venues?.map((v) => <option key={v.value} value={v.value}>{v.value} ({v.count})</option>)}
            </select>
          </label>
          <label className={css.field}>
            <span>{t.libFieldVehicle}</span>
            <select className={css.input} value={filters.vehicle} onChange={setFilter('vehicle')}>
              <option value="">{t.libAll}</option>
              {facets?.vehicles?.map((v) => <option key={v.value} value={v.value}>{v.value} ({v.count})</option>)}
            </select>
          </label>
          <label className={css.field}>
            <span>{t.libFrom}</span>
            <input className={css.input} type="date" value={filters.from} onChange={setFilter('from')} />
          </label>
          <label className={css.field}>
            <span>{t.libTo}</span>
            <input className={css.input} type="date" value={filters.to} onChange={setFilter('to')} />
          </label>
          {filtered && (
            <button type="button" className="ui-btn ui-btn--sm ui-btn--ghost" onClick={clearFilters}>
              <Icon name="x" size={12} /> {t.libClearFilters}
            </button>
          )}
        </div>

        {rowError && <div className={css.rowErr} role="alert"><Icon name="alert" size={14} /> {rowError}</div>}

        {res.error && !loading && (
          <div className={css.stateBox} role="alert">
            <Icon name="alert" size={22} />
            <div>{res.error}</div>
            <button type="button" className="ui-btn ui-btn--sm" onClick={refresh}>{t.libRetry}</button>
          </div>
        )}

        {loading && !res.data && !res.error && (
          <div className={css.stateBox} role="status"><span className="shell-spin" /> {t.libLoading}</div>
        )}

        {!res.error && res.data && items.length === 0 && (
          <EmptyState icon="layers">
            {filtered ? t.libEmptyFiltered : t.libEmpty}
          </EmptyState>
        )}

        {items.length > 0 && (
          <div className={`${css.tableWrap}${loading ? ` ${css.dim}` : ''}`}>
            <table className="ui-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }} aria-label={t.libColCompare} />
                  <th>{t.libColSession}</th>
                  <th>{t.libFieldVenue}</th>
                  <th>{t.libFieldVehicle}</th>
                  <th>{t.libColDate}</th>
                  <th className="is-num">{t.bestLap}</th>
                  <th className="is-num">{t.libColLaps}</th>
                  <th className={css.actionsCol}>{t.libColActions}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const isEditing = editing?.id === row.id;
                  const isConfirm = confirmId === row.id;
                  const busy = busyId === row.id;
                  return (
                    <tr key={row.id} className={row.id === openedId ? css.rowOpen : undefined}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.includes(row.id)}
                          onChange={() => toggleSel(row)}
                          aria-label={`${t.libColCompare}: ${row.title}`}
                        />
                      </td>
                      <td className={css.cellTitle}>
                        {isEditing ? (
                          <input
                            className={css.input}
                            autoFocus
                            value={editing.value}
                            maxLength={200}
                            onChange={(e) => setEditing({ id: row.id, value: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') commitRename();
                              if (e.key === 'Escape') setEditing(null);
                            }}
                            onBlur={commitRename}
                            aria-label={t.libRename}
                          />
                        ) : (
                          <>
                            <span className={css.title} title={row.title}>{row.title}</span>
                            {row.source_filename && <span className={css.file} title={row.source_filename}>{row.source_filename}</span>}
                          </>
                        )}
                      </td>
                      <td>{row.venue || <span className={css.dim}>—</span>}</td>
                      <td>{row.vehicle || <span className={css.dim}>—</span>}</td>
                      <td className={css.nowrap}>{fmtDate(row.created_at, lang)}</td>
                      <td className="is-num">{fmtLap(row.best_lap_s)}</td>
                      <td className="is-num">{row.n_laps ?? '—'}</td>
                      <td className={css.actionsCol}>
                        {isConfirm ? (
                          <span className={css.confirm}>
                            <span>{t.libDeleteConfirm}</span>
                            <button type="button" className={`ui-btn ui-btn--sm ${css.danger}`} onClick={() => remove(row)}>{t.libDelete}</button>
                            <button type="button" className="ui-btn ui-btn--sm ui-btn--ghost" onClick={() => setConfirmId(null)}>{t.libCancel}</button>
                          </span>
                        ) : (
                          <span className={css.actions}>
                            {row.id === openedId && <Badge tone="accent">{t.libOpenBadge}</Badge>}
                            <button type="button" className="ui-btn ui-btn--sm ui-btn--primary" disabled={busy} onClick={() => open(row)}>
                              {busy ? <span className="shell-spin" /> : <Icon name="upload" size={12} />} {t.libOpen}
                            </button>
                            <button type="button" className="ui-btn ui-btn--sm" disabled={busy} onClick={() => setEditing({ id: row.id, value: row.title })}>
                              {t.libRename}
                            </button>
                            <button type="button" className="ui-btn ui-btn--sm ui-btn--ghost" disabled={busy} onClick={() => setConfirmId(row.id)} aria-label={`${t.libDelete}: ${row.title}`}>
                              <Icon name="x" size={12} /> {t.libDelete}
                            </button>
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {total > PAGE && (
          <div className={css.pager}>
            <span>{t.libPageInfo(page + 1, pages, total)}</span>
            <button type="button" className="ui-btn ui-btn--sm" disabled={page === 0} onClick={() => setPage(page - 1)}>{t.libPrev}</button>
            <button type="button" className="ui-btn ui-btn--sm" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>{t.libNext}</button>
          </div>
        )}
      </Panel>
    </div>
  );
}
