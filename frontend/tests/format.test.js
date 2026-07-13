import assert from 'node:assert/strict'
import test from 'node:test'
import { formatKg, formatNumber, formatPercent, humanize, statusTone } from '../src/lib/format.js'

test('formats dashboard numbers defensively', () => {
  assert.equal(formatNumber('1234.56', 1), '1,234.6')
  assert.equal(formatNumber('not-a-number'), '0')
  assert.equal(formatKg(12.34), '12.3 kg')
  assert.equal(formatPercent(87.65), '87.7%')
})

test('humanizes backend enum values', () => {
  assert.equal(humanize('READY_FOR_PICKUP'), 'Ready For Pickup')
  assert.equal(humanize('camera_offline'), 'Camera Offline')
})

test('maps operational states to consistent tones', () => {
  assert.equal(statusTone('ACTIVE'), 'positive')
  assert.equal(statusTone('NEAR_FULL'), 'warning')
  assert.equal(statusTone('REJECTED'), 'danger')
  assert.equal(statusTone('UNKNOWN'), 'neutral')
})
