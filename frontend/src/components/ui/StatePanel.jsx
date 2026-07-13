const StatePanel = ({ action, actionLabel, compact = false, message, title, tone = 'neutral' }) => (
  <div className={`state-panel state-${tone} ${compact ? 'state-compact' : ''}`} role={tone === 'danger' ? 'alert' : 'status'}>
    <strong>{title}</strong>
    {message && <p>{message}</p>}
    {action && <button className="button button-secondary button-small" type="button" onClick={action}>{actionLabel}</button>}
  </div>
)

export default StatePanel
