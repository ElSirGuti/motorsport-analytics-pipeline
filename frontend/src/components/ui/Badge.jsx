/** tone: accent|ok|warn|bad (default neutral) */
export default function Badge({ tone, children, title }) {
  return <span className={`ui-badge${tone ? ` ui-badge--${tone}` : ''}`} title={title}>{children}</span>;
}
