import { useMemo, useState } from 'react'
import campusMap from '../../assets/hcmut-campus-map.jpg'
import {
  CAMPUS_GATES,
  CAMPUS_HUBS,
  hydrateCampusHubs,
  optimizeCampusRoute,
  pointPosition,
  routePath,
} from '../../lib/campusRoute'
import { formatDateTime, formatKg, formatNumber, formatPercent } from '../../lib/format'
import StatePanel from '../ui/StatePanel'
import StatusBadge from '../ui/StatusBadge'

const RoutesPanel = ({ hubs = [], routes = [] }) => {
  const [gateId, setGateId] = useState(CAMPUS_GATES[0].id)
  const [selectedHubIds, setSelectedHubIds] = useState(() => CAMPUS_HUBS.map((hub) => hub.mapId))
  const campusHubs = useMemo(() => hydrateCampusHubs(hubs), [hubs])
  const selectedHubs = useMemo(
    () => campusHubs.filter((hub) => selectedHubIds.includes(hub.mapId)),
    [campusHubs, selectedHubIds],
  )
  const plan = useMemo(
    () => optimizeCampusRoute({ gateId, hubs: selectedHubs }),
    [gateId, selectedHubs],
  )
  const path = routePath(plan.points)
  const stopSequence = new Map(plan.stops.map((hub, index) => [hub.mapId, index + 1]))
  const hubName = (id) => hubs.find((hub) => hub.id === id)?.name || 'Unknown Hub'

  const toggleHub = (mapId) => {
    setSelectedHubIds((current) => (
      current.includes(mapId)
        ? current.filter((item) => item !== mapId)
        : [...current, mapId]
    ))
  }

  return (
    <div className="panel-stack">
      <section className="panel-card campus-route-card">
        <div className="card-heading campus-route-heading">
          <div>
            <span className="card-kicker">Interactive campus collection prototype</span>
            <h2>Optimized HCMUT collection route</h2>
            <p>Choose a starting gate and the simulator evaluates every stop order over mapped campus corridors.</p>
          </div>
          <label className="gate-selector">
            <span>Start and return gate</span>
            <select value={gateId} onChange={(event) => setGateId(event.target.value)}>
              {CAMPUS_GATES.map((gate) => <option key={gate.id} value={gate.id}>{gate.name}</option>)}
            </select>
          </label>
        </div>

        <div className="campus-route-layout">
          <div className="campus-map-shell">
            <img alt="HCMUT campus schematic used for the route prototype" src={campusMap} />
            <svg aria-hidden="true" className="campus-route-overlay" preserveAspectRatio="xMidYMid meet" viewBox="0 0 1200 900">
              {plan.points.length > 1 && (
                <>
                  <path className="campus-route-shadow" d={path} />
                  <path className="campus-route-line" d={path} />
                  <circle className="route-vehicle" r="11">
                    <animateMotion dur="9s" path={path} repeatCount="indefinite" />
                  </circle>
                </>
              )}
            </svg>

            {CAMPUS_GATES.map((gate) => (
              <button
                aria-label={`Start route from ${gate.name}`}
                className={`map-gate-node ${gate.id === plan.gate.id ? 'selected' : ''}`}
                key={gate.id}
                onClick={() => setGateId(gate.id)}
                style={pointPosition(gate)}
                title={gate.name}
                type="button"
              >
                {gate.shortLabel}
              </button>
            ))}

            {campusHubs.map((hub) => {
              const selected = selectedHubIds.includes(hub.mapId)
              const sequence = stopSequence.get(hub.mapId)
              return (
                <button
                  aria-pressed={selected}
                  className={`map-hub-node ${selected ? 'selected' : 'disabled'} ${hub.fillLevel >= 80 ? 'near-full' : ''}`}
                  key={hub.mapId}
                  onClick={() => toggleHub(hub.mapId)}
                  style={pointPosition(hub)}
                  title={`${hub.name}: ${formatPercent(hub.fillLevel)} full`}
                  type="button"
                >
                  <span>{sequence || hub.mapId}</span>
                  <small>{hub.mapId}</small>
                </button>
              )
            })}

            <div className="campus-map-legend">
              <span><i className="legend-route" /> Optimized loop</span>
              <span><i className="legend-gate" /> Selected gate</span>
              <span><i className="legend-hub" /> Collection Hub</span>
            </div>
          </div>

          <aside className="route-plan-panel">
            <div className="route-plan-summary">
              <span>Shortest mapped loop</span>
              <strong>{formatNumber(plan.distanceKm, 2)} km</strong>
              <small>{plan.gate.name} · returns to start</small>
            </div>

            <div className="route-stat-grid">
              <div><span>Selected stops</span><strong>{plan.stops.length}</strong></div>
              <div><span>Estimated time</span><strong>{plan.estimatedMinutes} min</strong></div>
              <div><span>Expected load</span><strong>{formatKg(plan.estimatedLoadKg)}</strong></div>
              <div><span>vs fixed order</span><strong>{formatPercent(plan.savedPercent)}</strong></div>
            </div>

            <ol className="campus-stop-list">
              <li className="gate-stop">
                <span>G</span>
                <div><strong>{plan.gate.name}</strong><small>Vehicle departure</small></div>
              </li>
              {plan.stops.map((hub, index) => (
                <li key={hub.mapId}>
                  <span>{index + 1}</span>
                  <div><strong>{hub.mapId} · {hub.name}</strong><small>{formatKg(hub.expectedLoadKg)} · {formatPercent(hub.fillLevel)} full</small></div>
                  <StatusBadge status={hub.status} />
                </li>
              ))}
              <li className="gate-stop return-stop">
                <span>↺</span>
                <div><strong>Return to {plan.gate.shortLabel}</strong><small>Collection loop completed</small></div>
              </li>
            </ol>

            <div className="hub-toggle-grid">
              {campusHubs.map((hub) => (
                <label key={hub.mapId}>
                  <input
                    checked={selectedHubIds.includes(hub.mapId)}
                    onChange={() => toggleHub(hub.mapId)}
                    type="checkbox"
                  />
                  <span>{hub.mapId}</span>
                </label>
              ))}
            </div>

            <p className="route-method-note">
              Prototype method: exhaustive stop-order comparison over a hand-mapped campus corridor graph. The overlay follows passable corridors and avoids building footprints; a field pilot will replace the schematic graph with surveyed distances and access restrictions.
            </p>
          </aside>
        </div>
      </section>

      <section className="panel-card">
        <div className="card-heading">
          <div><span className="card-kicker">Threshold-based logistics</span><h2>Route operations history</h2></div>
          <span className="summary-chip">{routes.filter((route) => route.status === 'IN_PROGRESS').length} active</span>
        </div>
        {!routes.length ? (
          <StatePanel title="No collection routes yet" message="When a Hub reaches its pickup threshold, an operational route will appear here." />
        ) : (
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
                    {[...route.stops].sort((a, b) => a.sequence - b.sequence).map((stop) => (
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
        )}
      </section>
    </div>
  )
}

export default RoutesPanel
