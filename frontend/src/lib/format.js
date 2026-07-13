export const formatNumber = (value, maximumFractionDigits = 0) => {
  const numeric = Number(value ?? 0)
  return new Intl.NumberFormat('en-US', { maximumFractionDigits }).format(
    Number.isFinite(numeric) ? numeric : 0,
  )
}

export const formatKg = (value) => `${formatNumber(value, 1)} kg`

export const formatPercent = (value) => `${formatNumber(value, 1)}%`

export const formatDateTime = (value) => {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Invalid date'
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export const humanize = (value) =>
  String(value ?? '')
    .toLowerCase()
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())

export const statusTone = (status) => {
  const normalized = String(status ?? '').toUpperCase()
  if (['ACTIVE', 'COMPLETED', 'ACCEPTED', 'RECEIVED', 'ONLINE'].includes(normalized)) {
    return 'positive'
  }
  if (['NEAR_FULL', 'IN_PROGRESS', 'PLANNED', 'READY_FOR_PICKUP'].includes(normalized)) {
    return 'warning'
  }
  if (['FULL', 'OFFLINE', 'REJECTED', 'CANCELLED'].includes(normalized)) {
    return 'danger'
  }
  return 'neutral'
}

export const downloadCsv = (filename, rows) => {
  if (!rows.length) return
  const keys = Object.keys(rows[0])
  const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const csv = [keys.map(escape).join(','), ...rows.map((row) => keys.map((key) => escape(row[key])).join(','))].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
