import assert from 'node:assert/strict'
import test from 'node:test'
import { buildMockEsg, buildMockSummary, getMockTraceability, mockHubs } from '../src/api/mockData.js'

test('keeps demo reporting periods internally consistent', () => {
  const day = buildMockSummary('day')
  const week = buildMockSummary('week')
  const month = buildMockSummary('month')

  assert.equal(day.accepted_bottles + day.rejected_bottles, day.transactions_in_period)
  assert.ok(week.transactions_in_period > day.transactions_in_period)
  assert.ok(month.recovered_weight_kg > week.recovered_weight_kg)
})

test('builds an ESG report from the same period summary', () => {
  const summary = buildMockSummary('week')
  const report = buildMockEsg('week')

  assert.equal(report.total_transactions, summary.transactions_in_period)
  assert.equal(report.total_plastic_recovered_kg, summary.recovered_weight_kg)
  assert.equal(report.period, 'week')
})

test('demo hubs expose the telemetry fields expected by the backend contract', () => {
  assert.ok(mockHubs.length >= 3)
  for (const hub of mockHubs) {
    assert.equal(typeof hub.camera_online, 'boolean')
    assert.equal(typeof hub.sensor_online, 'boolean')
    assert.ok(Number(hub.fill_level) >= 0 && Number(hub.fill_level) <= 100)
  }
})

test('traceability demo accepts only its documented sample code', () => {
  assert.equal(getMockTraceability('TRACE-PET-240713-001').events.length, 4)
  assert.throws(() => getMockTraceability('missing'), /not found/i)
})
