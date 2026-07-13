import { formatDateTime, formatKg, formatNumber, formatPercent } from '../../lib/format'
import StatePanel from '../ui/StatePanel'
import StatusBadge from '../ui/StatusBadge'

const RoutesPanel = ({ hubs, routes }) => {
  const hubName = (id) => hubs.find((hub) => hub.id === id)?.name || 'Unknown Hub'

  if (!routes.length) return <StatePanel title="No collection routes yet" message="When a Hub reaches its pickup threshold, an optimized route will appear here." />

  return (
    <div className="panel-stack">
      <section className="panel-card">
        <div className="card-heading">
          <div><span className="card-kicker">Threshold-based logistics</span><h2>Collection routes</h2></div>
          <span className="summary-chip">{routes.filter((route) => route.status === 'IN_PROGRESS').length} active</span>
        </div>
        <div className="route-card-grid">
          {routes.map((route) => (
            <article className="route-card" key={route.id}>
              <div className="route-card-head"><div><strong>{route.code}</strong><small>Planned {formatDateTime(route.planned_at)}</small></div><StatusBadge status={route.status} /></div>
              <div className="route-score"><strong>{formatPercent(route.distance_saved_percent)}</strong><span>distance saved</span></div>
              <dl className="definition-grid">
                <div><dt>Optimized</dt><dd>{formatNumber(route.total_distance_km, 1)} km</dd></div>
                <div><dt>Baseline</dt><dd>{formatNumber(route.baseline_distance_km, 1)} km</dd></div>
                <div><dt>Expected load</dt><dd>{formatKg(route.estimated_load_kg)}</dd></div>
                <div><dt>Trigger</dt><dd>{formatPercent(route.threshold_percent)}</dd></div>
              </dl>
              {route.stops?.length > 0 && (
                <ol className="route-stops">
                  {route.stops.sort((a, b) => a.sequence - b.sequence).map((stop) => (
                    <li key={stop.id}>
                      <span>{stop.sequence}</span>
                      <div><strong>{hubName(stop.hub_id)}</strong><small>{formatKg(stop.expected_load_kg)} expected</small></div>
                      <StatusBadge status={stop.collected_at ? 'COMPLETED' : 'PLANNED'} />
                    </li>
                  ))}
                </ol>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

export default RoutesPanel
