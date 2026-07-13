import { Doughnut } from 'react-chartjs-2'
import { formatKg, formatNumber, formatPercent, humanize } from '../../lib/format'
import MetricCard from '../ui/MetricCard'
import StatusBadge from '../ui/StatusBadge'

const OverviewPanel = ({ hubs, summary }) => {
  const materialTotal = Number(summary.pet_bottles || 0) + Number(summary.hdpe_bottles || 0)
  const materialData = {
    labels: ['PET', 'HDPE'],
    datasets: [{
      data: [summary.pet_bottles || 0, summary.hdpe_bottles || 0],
      backgroundColor: ['#36d48f', '#58a6ff'],
      borderColor: ['#0f2a20', '#0f2a20'],
      borderWidth: 4,
      hoverOffset: 4,
    }],
  }

  return (
    <div className="panel-stack">
      <section className="metrics-grid" aria-label="Key performance indicators">
        <MetricCard label="Plastic recovered" value={formatKg(summary.recovered_weight_kg)} detail={`${formatNumber(materialTotal)} verified bottles`} />
        <MetricCard accent="blue" label="Participants" value={formatNumber(summary.participants)} detail={`${formatNumber(summary.transactions_in_period)} return attempts`} />
        <MetricCard accent="purple" label="Successful transactions" value={formatNumber(summary.successful_transactions)} detail={`${formatPercent(summary.success_rate_percent)} acceptance rate`} />
        <MetricCard accent="amber" label="Estimated CO₂ saved" value={formatKg(summary.estimated_co2_saved_kg)} detail={`${formatKg(summary.recovered_weight_kg)} recovered material`} />
        <MetricCard accent="cyan" label="Distance saved" value={`${formatNumber(summary.distance_saved_km, 1)} km`} detail={`${formatPercent(summary.distance_saved_percent)} against baseline`} />
        <MetricCard accent="rose" label="Traceability complete" value={formatPercent(summary.traceability_completeness_percent)} detail={`${formatNumber(summary.ready_batches)} batch ready for pickup`} />
      </section>

      <section className="content-grid content-grid-2">
        <article className="panel-card chart-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">Material mix</span>
              <h2>PET and HDPE returns</h2>
            </div>
            <span className="summary-chip">{formatNumber(materialTotal)} bottles</span>
          </div>
          <div className="donut-layout">
            <div className="donut-wrap">
              <Doughnut
                data={materialData}
                options={{
                  cutout: '72%',
                  maintainAspectRatio: false,
                  plugins: { legend: { display: false } },
                }}
              />
            </div>
            <div className="legend-list">
              <div><span className="legend-dot pet" /><strong>PET</strong><span>{formatNumber(summary.pet_bottles)}</span></div>
              <div><span className="legend-dot hdpe" /><strong>HDPE</strong><span>{formatNumber(summary.hdpe_bottles)}</span></div>
              <p>Only verified PET and HDPE bottles are counted in recovered material.</p>
            </div>
          </div>
        </article>

        <article className="panel-card">
          <div className="card-heading">
            <div>
              <span className="card-kicker">Logistics efficiency</span>
              <h2>Route against baseline</h2>
            </div>
          </div>
          <div className="route-comparison">
            <div>
              <span>Baseline route</span>
              <strong>{formatNumber(summary.baseline_distance_km, 1)} km</strong>
              <div className="progress-track"><span style={{ width: '100%' }} /></div>
            </div>
            <div>
              <span>Optimized route</span>
              <strong>{formatNumber(summary.optimized_distance_km, 1)} km</strong>
              <div className="progress-track progress-green"><span style={{ width: `${Math.min(100, (Number(summary.optimized_distance_km || 0) / Math.max(1, Number(summary.baseline_distance_km || 1))) * 100)}%` }} /></div>
            </div>
          </div>
          <dl className="definition-grid">
            <div><dt>Collection efficiency</dt><dd>{formatNumber(summary.collection_efficiency_kg_per_km, 1)} kg/km</dd></div>
            <div><dt>Vehicle utilization</dt><dd>{formatPercent(summary.vehicle_utilization_percent)}</dd></div>
            <div><dt>Completed routes</dt><dd>{formatNumber(summary.completed_routes)}</dd></div>
            <div><dt>Active pickups</dt><dd>{formatNumber(summary.active_pickups)}</dd></div>
          </dl>
        </article>
      </section>

      <section className="panel-card">
        <div className="card-heading">
          <div>
            <span className="card-kicker">Live operations</span>
            <h2>Campus Hub readiness</h2>
          </div>
          <span className="summary-chip">{hubs.length} monitored</span>
        </div>
        <div className="hub-snapshot-grid">
          {hubs.slice(0, 4).map((hub) => (
            <article className="hub-snapshot" key={hub.id}>
              <div><strong>{hub.name}</strong><small>{hub.location_name}</small></div>
              <StatusBadge status={hub.status} />
              <div className="fill-row"><span>Fill level</span><strong>{formatPercent(hub.fill_level)}</strong></div>
              <div className="progress-track"><span style={{ width: `${Math.min(100, Number(hub.fill_level || 0))}%` }} /></div>
              <small>{hub.camera_online && hub.sensor_online ? 'Camera and sensor online' : humanize(hub.status)}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

export default OverviewPanel
