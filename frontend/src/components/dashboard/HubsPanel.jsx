import { Line } from 'react-chartjs-2'
import { formatDateTime, formatKg, formatNumber, formatPercent } from '../../lib/format'
import StatePanel from '../ui/StatePanel'
import StatusBadge from '../ui/StatusBadge'

const HubsPanel = ({ hubs, loadingTelemetry, onSelectHub, selectedHub, telemetry }) => {
  const orderedTelemetry = [...telemetry].reverse()
  const chartData = {
    labels: orderedTelemetry.map((item) => new Date(item.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })),
    datasets: [
      { label: 'Fill level (%)', data: orderedTelemetry.map((item) => Number(item.fill_level)), borderColor: '#36d48f', backgroundColor: 'rgba(54, 212, 143, .12)', fill: true, tension: 0.3 },
      { label: 'Weight (kg)', data: orderedTelemetry.map((item) => Number(item.weight_kg)), borderColor: '#58a6ff', backgroundColor: 'transparent', tension: 0.3 },
    ],
  }

  return (
    <div className="panel-stack">
      <section className="panel-card">
        <div className="card-heading">
          <div><span className="card-kicker">Smart RVM network</span><h2>Hub status and pickup readiness</h2></div>
          <span className="summary-chip">{hubs.filter((hub) => hub.camera_online && hub.sensor_online).length}/{hubs.length} fully online</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Hub</th><th>Status</th><th>Fill</th><th>Load</th><th>Camera</th><th>Sensor</th><th>Last seen</th><th /></tr></thead>
            <tbody>
              {hubs.map((hub) => (
                <tr key={hub.id}>
                  <td><strong>{hub.name}</strong><small>{hub.code} · {hub.location_name}</small></td>
                  <td><StatusBadge status={hub.status} /></td>
                  <td><strong>{formatPercent(hub.fill_level)}</strong><div className="mini-progress"><span style={{ width: `${Math.min(100, Number(hub.fill_level || 0))}%` }} /></div></td>
                  <td>{formatKg(hub.current_load_kg)}</td>
                  <td><span className={`signal ${hub.camera_online ? 'online' : 'offline'}`} />{hub.camera_online ? 'Online' : 'Offline'}</td>
                  <td><span className={`signal ${hub.sensor_online ? 'online' : 'offline'}`} />{hub.sensor_online ? 'Online' : 'Offline'}</td>
                  <td>{formatDateTime(hub.last_seen_at)}</td>
                  <td><button className="button button-secondary button-small" type="button" onClick={() => onSelectHub(hub)}>Inspect</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selectedHub && (
        <section className="panel-card">
          <div className="card-heading">
            <div><span className="card-kicker">Telemetry history</span><h2>{selectedHub.name}</h2></div>
            <div className="sensor-summary"><span>{formatNumber(selectedHub.pet_current)} PET</span><span>{formatNumber(selectedHub.hdpe_current)} HDPE</span></div>
          </div>
          {loadingTelemetry ? (
            <StatePanel compact title="Loading telemetry…" />
          ) : telemetry.length ? (
            <div className="line-chart"><Line data={chartData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: '#8fa99d' } } }, scales: { x: { ticks: { color: '#789286' }, grid: { color: 'rgba(143,169,157,.08)' } }, y: { beginAtZero: true, ticks: { color: '#789286' }, grid: { color: 'rgba(143,169,157,.08)' } } } }} /></div>
          ) : (
            <StatePanel compact title="No readings in this period" message="The Hub is known, but no telemetry points were recorded for the selected calendar window." />
          )}
        </section>
      )}
    </div>
  )
}

export default HubsPanel
