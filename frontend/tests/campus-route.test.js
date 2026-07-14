import assert from 'node:assert/strict'
import test from 'node:test'
import {
  CAMPUS_GATES,
  CAMPUS_HUBS,
  hydrateCampusHubs,
  optimizeCampusRoute,
  routeDistanceKm,
  routePath,
  shortestRoadLeg,
} from '../src/lib/campusRoute.js'

test('optimizer returns every selected Hub exactly once and closes the loop', () => {
  const hubs = hydrateCampusHubs([])

  for (const gate of CAMPUS_GATES) {
    const plan = optimizeCampusRoute({ gateId: gate.id, hubs })
    assert.equal(plan.gate.id, gate.id)
    assert.equal(plan.stops.length, CAMPUS_HUBS.length)
    assert.deepEqual(new Set(plan.stops.map((hub) => hub.mapId)), new Set(CAMPUS_HUBS.map((hub) => hub.mapId)))
    assert.equal(plan.points[0].id, gate.id)
    assert.equal(plan.points.at(-1).id, gate.id)
  }
})

test('optimized route is never longer than the fixed H1-H4 baseline', () => {
  const hubs = hydrateCampusHubs([])

  for (const gate of CAMPUS_GATES) {
    const plan = optimizeCampusRoute({ gateId: gate.id, hubs })
    assert.ok(plan.distanceKm <= routeDistanceKm(plan.gate, hubs) + Number.EPSILON)
    assert.ok(plan.savedPercent >= 0)
  }
})

test('optimizer supports a selected Hub subset and creates an SVG path', () => {
  const hubs = hydrateCampusHubs([]).slice(1, 3)
  const plan = optimizeCampusRoute({ gateId: 'gate-2', hubs })

  assert.equal(plan.stops.length, 2)
  assert.ok(plan.points.length > 4)
  assert.equal(plan.points[0].id, 'gate-2')
  assert.equal(plan.points.at(-1).id, 'gate-2')
  assert.match(routePath(plan.points), /^M \d+ \d+( L \d+ \d+)+$/)
  assert.ok(plan.estimatedLoadKg > 0)
  assert.ok(plan.estimatedMinutes > 0)
})

test('every gate-to-Hub leg follows mapped corridors through intermediate waypoints', () => {
  const gate = CAMPUS_GATES[0]

  for (const hub of CAMPUS_HUBS) {
    const leg = shortestRoadLeg(gate, hub)
    assert.equal(leg.points[0].id, gate.id)
    assert.equal(leg.points.at(-1).id, hub.mapId)
    assert.ok(leg.points.length >= 3)
    assert.ok(leg.distanceKm > 0)
  }
})

test('empty selection produces a zero-distance gate-only plan', () => {
  const plan = optimizeCampusRoute({ gateId: 'gate-3', hubs: [] })

  assert.equal(plan.distanceKm, 0)
  assert.equal(plan.estimatedMinutes, 0)
  assert.equal(plan.points.length, 1)
  assert.equal(plan.points[0].id, 'gate-3')
})
