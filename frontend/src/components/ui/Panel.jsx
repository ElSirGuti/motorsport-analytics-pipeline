import Icon from './Icon.jsx';

/** Standard card: header (icon, title, subtitle, actions) + body. */
export default function Panel({ icon, title, subtitle, actions, children, bodyClassName = '', className = '', id, flush = false }) {
  return (
    <section id={id} className={`ui-panel ${className}`.trim()}>
      {(title || actions) && (
        <header className="ui-panel__head">
          {icon && <Icon name={icon} size={16} className="ui-panel__icon" />}
          <div>
            {title && <h3 className="ui-panel__title">{title}</h3>}
            {subtitle && <div className="ui-panel__sub">{subtitle}</div>}
          </div>
          {actions && <div className="ui-panel__actions">{actions}</div>}
        </header>
      )}
      <div className={flush ? bodyClassName : `ui-panel__body ${bodyClassName}`.trim()}>{children}</div>
    </section>
  );
}
