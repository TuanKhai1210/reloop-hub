const MetricCard = ({ accent = 'green', detail, label, value }) => (
  <article className={`metric-card metric-${accent}`}>
    <span className="metric-label">{label}</span>
    <strong>{value}</strong>
    {detail && <small>{detail}</small>}
  </article>
)

export default MetricCard
