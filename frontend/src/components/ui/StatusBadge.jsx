import { humanize, statusTone } from '../../lib/format'

const StatusBadge = ({ status }) => <span className={`status-badge status-${statusTone(status)}`}>{humanize(status)}</span>

export default StatusBadge
