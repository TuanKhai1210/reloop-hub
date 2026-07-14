import { useState } from 'react'
import { formatDateTime, humanize } from '../../lib/format'
import StatePanel from '../ui/StatePanel'
import StatusBadge from '../ui/StatusBadge'

const TraceabilityPanel = ({ demoMode, onLookup }) => {
  const [traceCode, setTraceCode] = useState(demoMode ? 'TRACE-PET-240713-001' : '')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const lookup = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      setResult(await onLookup(traceCode))
    } catch (lookupError) {
      setResult(null)
      setError(lookupError.message || 'Trace code could not be found.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel-stack">
      <section className="trace-search-card">
        <div><span className="card-kicker">Material passport</span><h2>Trace a verified bottle or batch</h2><p>Follow recorded events from Hub acceptance through batch aggregation, pickup and recycler receipt.</p></div>
        <form onSubmit={lookup}>
          <label htmlFor="trace-code">Trace code</label>
          <div><input id="trace-code" value={traceCode} onChange={(event) => setTraceCode(event.target.value)} placeholder="e.g. TRACE-PET-240713-001" required /><button className="button button-primary" type="submit" disabled={loading}>{loading ? 'Tracing…' : 'Trace material'}</button></div>
          {demoMode && <small>Demo code: TRACE-PET-240713-001</small>}
        </form>
      </section>

      {error && <StatePanel tone="danger" title="Trace lookup failed" message={error} />}
      {result && (
        <section className="panel-card">
          <div className="card-heading"><div><span className="card-kicker">Trace result</span><h2><code>{result.trace_code}</code></h2></div><StatusBadge status={result.current_stage} /></div>
          <ol className="timeline">
            {result.events.map((event, index) => (
              <li key={`${event.stage}-${event.occurred_at}-${index}`}>
                <span className="timeline-dot" />
                <div className="timeline-card">
                  <div><strong>{humanize(event.stage)}</strong><time>{formatDateTime(event.occurred_at)}</time></div>
                  <p>{event.notes || 'Stage recorded without additional notes.'}</p>
                  <small>{humanize(event.location_type)} · {event.location_ref}</small>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}

export default TraceabilityPanel
