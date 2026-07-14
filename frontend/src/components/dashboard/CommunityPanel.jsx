import { formatNumber } from '../../lib/format'
import MetricCard from '../ui/MetricCard'
import StatePanel from '../ui/StatePanel'
import StatusBadge from '../ui/StatusBadge'

const CommunityPanel = ({ summary, users, vouchers }) => (
  <div className="panel-stack">
    <section className="metrics-grid metrics-grid-4">
      <MetricCard label="Registered users" value={formatNumber(summary.users)} detail={`${formatNumber(summary.participants)} participated this period`} />
      <MetricCard accent="blue" label="Return attempts" value={formatNumber(summary.transactions_in_period)} detail={`${formatNumber(summary.successful_transactions)} successful`} />
      <MetricCard accent="purple" label="Active vouchers" value={formatNumber(vouchers.length)} detail={`${formatNumber(vouchers.reduce((total, voucher) => total + Number(voucher.quantity_available || 0), 0))} rewards available`} />
      <MetricCard accent="amber" label="Repeat behavior proxy" value={formatNumber(users.filter((item) => Number(item.total_bottles_returned) >= 10).length)} detail="Users with at least 10 verified returns" />
    </section>

    <section className="content-grid content-grid-2">
      <article className="panel-card">
        <div className="card-heading"><div><span className="card-kicker">Campus community</span><h2>Users and verified behavior</h2></div></div>
        {users.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>User</th><th>Role</th><th>Verified bottles</th><th>Points balance</th><th>Status</th></tr></thead>
              <tbody>{users.map((person) => (
                <tr key={person.id}>
                  <td><strong>{person.name}</strong><small>{person.student_code || person.email || 'No identifier'}</small></td>
                  <td>{person.role}</td>
                  <td>{formatNumber(person.total_bottles_returned)}</td>
                  <td>{formatNumber(person.points_balance)}</td>
                  <td><StatusBadge status={person.is_active ? 'ACTIVE' : 'OFFLINE'} /></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <StatePanel compact title="User list unavailable for this role" message="Recycler accounts can access material and ESG evidence but cannot enumerate platform users." />}
      </article>

      <article className="panel-card">
        <div className="card-heading"><div><span className="card-kicker">Green Points wallet</span><h2>Canteen-linked rewards</h2></div></div>
        <div className="voucher-list">
          {vouchers.map((voucher) => (
            <article key={voucher.id}>
              <div><strong>{voucher.name}</strong><small>{voucher.partner_name}</small></div>
              <div><strong>{formatNumber(voucher.required_points)} pts</strong><small>{voucher.value_text}</small></div>
              <span>{formatNumber(voucher.quantity_available)} left</span>
            </article>
          ))}
        </div>
        <p className="panel-note">Rewards are partner-funded behavior incentives. They are not presented as being financed by plastic resale alone.</p>
      </article>
    </section>
  </div>
)

export default CommunityPanel
