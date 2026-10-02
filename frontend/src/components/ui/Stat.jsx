/** KPI: small caps label, big tabular value, optional hint. tone: ok|warn|bad|accent */
export default function Stat({ label, value, hint, tone }) {
  return (
    <div className="ui-stat">
      <span className="ui-stat__label">{label}</span>
      <span className={`ui-stat__value${tone ? ` ui-stat__value--${tone}` : ''}`}>{value}</span>
      {hint && <span className="ui-stat__hint">{hint}</span>}
    </div>
  );
}
