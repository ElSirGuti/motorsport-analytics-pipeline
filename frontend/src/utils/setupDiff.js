// What changed between two parsed Assetto Corsa setups (the objects of /api/setups/*).
const num = (v) => (typeof v === 'number' ? v : Number(v));

/** [{key, label, unit, from, to}] for every parameter whose value differs (parameters on one side only count). */
export function setupDiff(a, b) {
  if (!a?.params || !b?.params) return [];
  const out = [];
  const keys = new Set([...Object.keys(a.params), ...Object.keys(b.params)]);
  keys.forEach((k) => {
    const pa = a.params[k];
    const pb = b.params[k];
    const va = pa?.value;
    const vb = pb?.value;
    if (va === vb) return;
    if (Number.isFinite(num(va)) && Number.isFinite(num(vb)) && Math.abs(num(va) - num(vb)) < 1e-9) return;
    const p = pb || pa;
    out.push({ key: k, label: p.label || k, unit: p.unit || '', group: p.group || '', from: va ?? null, to: vb ?? null });
  });
  return out.sort((x, y) => x.group.localeCompare(y.group) || x.label.localeCompare(y.label));
}
