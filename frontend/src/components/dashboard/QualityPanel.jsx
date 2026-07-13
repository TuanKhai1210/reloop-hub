import { formatDateTime, formatNumber, formatPercent, humanize } from '../../lib/format'
import MetricCard from '../ui/MetricCard'
import StatePanel from '../ui/StatePanel'
import StatusBadge from '../ui/StatusBadge'

const QualityPanel = ({ deposits, summary }) => {
  const rejectionEntries = Object.entries(summary.rejection_reasons || {})
  const totalRejections = rejectionEntries.reduce((total, [, count]) => total + Number(count), 0)

  return (
    <div className="panel-stack">
      <section className="metrics-grid metrics-grid-4">
        <MetricCard label="Acceptance rate" value={formatPercent(summary.success_rate_percent)} detail={`${formatNumber(summary.accepted_bottles)} accepted`} />
        <MetricCard accent="blue" label="Average AI confidence" value={formatPercent(Number(summary.average_ai_confidence || 0) * 100)} detail="Multi-signal verification output" />
        <MetricCard accent="purple" label="Average cleanliness" value={formatPercent(Number(summary.average_cleanliness_score || 0) * 100)} detail="Accepted and inspected items" />
        <MetricCard accent="rose" label="Rejected bottles" value={formatNumber(summary.rejected_bottles)} detail={`${formatNumber(totalRejections)} classified reasons`} />
      </section>

      <section className="content-grid content-grid-2">
        <article className="panel-card">
          <div className="card-heading"><div><span className="card-kicker">Quality gate</span><h2>Why bottles were rejected</h2></div></div>
          {rejectionEntries.length ? (
            <div className="reason-list">
              {rejectionEntries.sort((a, b) => Number(b[1]) - Number(a[1])).map(([reason, count]) => (
                <div key={reason}>
                  <div><span>{humanize(reason)}</span><strong>{formatNumber(count)}</strong></div>
                  <div className="progress-track progress-danger"><span style={{ width: `${Math.max(6, (Number(count) / Math.max(1, totalRejections)) * 100)}%` }} /></div>
                </div>
              ))}
            </div>
          ) : (
            <StatePanel compact title="No rejection reasons recorded" />
          )}
        </article>

        <article className="panel-card quality-principle">
          <span className="card-kicker">Verification principle</span>
          <h2>No verification, no reward.</h2>
          <p>Camera or barcode signals support identification. Weight, cleanliness and anomaly rules protect the material stream. Uncertain cases are rejected or moved to review rather than silently rewarded.</p>
          <ul className="check-list">
            <li>Material restricted to PET and HDPE bottles</li>
            <li>Reward issued only after the Hub accepts the item</li>
            <li>Every decision retains confidence and item metadata</li>
            <li>Rejected items never enter a material batch</li>
          </ul>
        </article>
      </section>

      <section className="panel-card">
        <div className="card-heading"><div><span className="card-kicker">Bottle-level audit</span><h2>Recent verification transactions</h2></div><span className="summary-chip">Latest {deposits.length}</span></div>
        {deposits.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Trace code</th><th>Material</th><th>Result</th><th>Weight</th><th>AI confidence</th><th>Cleanliness</th><th>Points</th><th>Time</th></tr></thead>
              <tbody>{deposits.map((deposit) => (
                <tr key={deposit.id}>
                  <td><code>{deposit.code}</code></td>
                  <td>{deposit.verified_material_type || deposit.material_type}</td>
                  <td><StatusBadge status={deposit.status} /></td>
                  <td>{formatNumber(deposit.weight_gram, 1)} g</td>
                  <td>{formatPercent(Number(deposit.ai_confidence || 0) * 100)}</td>
                  <td>{formatPercent(Number(deposit.cleanliness_score || 0) * 100)}</td>
                  <td>{formatNumber(deposit.points_awarded)}</td>
                  <td>{formatDateTime(deposit.created_at)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <StatePanel compact title="No bottle transactions in this period" />}
      </section>
    </div>
  )
}

export default QualityPanel
