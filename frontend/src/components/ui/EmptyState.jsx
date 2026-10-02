import Icon from './Icon.jsx';

export default function EmptyState({ icon = 'info', children }) {
  return (
    <div className="ui-empty">
      <Icon name={icon} size={22} />
      <div>{children}</div>
    </div>
  );
}
