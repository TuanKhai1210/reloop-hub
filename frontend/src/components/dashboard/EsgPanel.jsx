import { downloadCsv, formatDateTime, formatKg, formatNumber, formatPercent } from '../../lib/format'
import MetricCard from '../ui/MetricCard'

const EsgPanel = ({ demoMode, report }) => {
  const exportReport = () => {
    const rows = Object.entries(report).map(([metric, value]) => ({ metric, value }))
    downloadCsv(`reloop-esg-${report.period}.csv`, rows)
  }

  return (
    <div className="panel-stack">
      <section className="report-header">
        <div>
          <span className="eyebrow">ESG-ready evidence</span>
          <h1>Environmental and operational report</h1>
          <p>{formatDateTime(report.period_start)} — {formatDateTime(report.period_end)} · {report.reporting_timezone}</p>
        </div>
        <button className="button button-secondary" type="button" onClick={exportReport}>Export CSV</button>
      </section>

      {demoMode && <div className="data-banner"><strong>Sample report</strong><span>Values demonstrate the reporting structure and are not measured pilot results.</span></div>}

      <section className="metrics-grid metrics-grid-4">
        <MetricCard label="Plastic recovered" value={formatKg(report.total_plastic_recovered_kg)} detail={`${formatNumber(report.pet_bottles)} PET · ${formatNumber(report.hdpe_bottles)} HDPE`} />
        <MetricCard accent="blue" label="Participants" value={formatNumber(report.participants)} detail={`${formatNumber(report.total_transactions)} transactions`} />
        <MetricCard accent="cyan" label="Distance saved" value={`${formatNumber(report.distance_saved_km, 1)} km`} detail={formatPercent(report.distance_saved_percent)} />
        <MetricCard accent="amber" label="Estimated CO₂ saved" value={formatKg(report.estimated_co2_saved_kg)} detail={`${formatNumber(report.co2_emission_factor_kg_per_km, 2)} kg CO₂/km factor`} />
      </section>

      <section className="content-grid content-grid-2">
        <article className="panel-card">
          <span className="card-kicker">Impact calculation</span>
          <h2>Transparent, reproducible metrics</h2>
          <div className="formula-box">CO₂ saved = (baseline distance − optimized distance) × emission factor</div>
          <dl className="report-definitions">
            <div><dt>Baseline distance</dt><dd>{formatNumber(report.baseline_distance_km, 1)} km</dd></div>
            <div><dt>Optimized distance</dt><dd>{formatNumber(report.optimized_distance_km, 1)} km</dd></div>
            <div><dt>Collection efficiency</dt><dd>{formatNumber(report.collection_efficiency_kg_per_km, 1)} kg/km</dd></div>
            <div><dt>Vehicle utilization</dt><dd>{formatPercent(report.vehicle_utilization_percent)}</dd></div>
          </dl>
        </article>
        <article className="panel-card">
          <span className="card-kicker">Evidence quality</span>
          <h2>What the report can substantiate</h2>
          <div className="evidence-score"><strong>{formatPercent(report.traceability_completeness_percent)}</strong><span>traceability completeness</span></div>
          <ul className="check-list">
            <li>{formatNumber(report.successful_transactions)} successful verified transactions</li>
            <li>{formatPercent(report.success_rate_percent)} transaction success rate</li>
            <li>{formatNumber(report.completed_routes)} completed collection routes</li>
            <li>{formatNumber(report.rejected_bottles)} rejected bottles excluded from feedstock</li>
          </ul>
        </article>
      </section>
    </div>
  )
}

export default EsgPanel
