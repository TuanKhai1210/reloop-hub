const periodMultiplier = { day: 1, week: 4.2, month: 14.8 }

const rounded = (value, digits = 0) => Number(value.toFixed(digits))

const baseSummary = {
  users: 236,
  participants: 42,
  active_hubs: 2,
  near_full_hubs: 1,
  offline_hubs: 0,
  camera_online_hubs: 3,
  sensor_online_hubs: 3,
  transactions_today: 126,
  transactions_in_period: 126,
  successful_transactions: 112,
  accepted_bottles: 112,
  rejected_bottles: 14,
  success_rate_percent: 88.9,
  pet_bottles: 86,
  hdpe_bottles: 26,
  recovered_weight_kg: 3.4,
  average_ai_confidence: 0.91,
  average_cleanliness_score: 0.87,
  rejection_reasons: {
    dirty_bottle: 7,
    liquid_detected: 4,
    foreign_object: 3,
  },
  ready_batches: 1,
  active_pickups: 1,
  completed_routes: 1,
  baseline_distance_km: 18.2,
  optimized_distance_km: 12.7,
  distance_saved_km: 5.5,
  distance_saved_percent: 30.2,
  collection_efficiency_kg_per_km: 4.8,
  vehicle_utilization_percent: 63.5,
  estimated_co2_saved_kg: 4.9,
  traceability_completeness_percent: 96.4,
}

export const mockHubs = [
  {
    id: '00000000-0000-0000-0000-000000000101',
    code: 'CANTEEN-01',
    name: 'Main Canteen Hub',
    location_name: 'HCMUT Main Canteen',
    status: 'NEAR_FULL',
    pet_capacity: 500,
    hdpe_capacity: 250,
    pet_current: 374,
    hdpe_current: 121,
    pickup_threshold_percent: 80,
    capacity_kg: 35,
    current_load_kg: 28.7,
    fill_level: 82,
    camera_online: true,
    sensor_online: true,
    last_seen_at: '2026-07-13T05:23:00Z',
  },
  {
    id: '00000000-0000-0000-0000-000000000102',
    code: 'DORM-01',
    name: 'Dormitory Hub',
    location_name: 'Campus Dormitory Lobby',
    status: 'ACTIVE',
    pet_capacity: 500,
    hdpe_capacity: 250,
    pet_current: 188,
    hdpe_current: 74,
    pickup_threshold_percent: 80,
    capacity_kg: 35,
    current_load_kg: 15.8,
    fill_level: 45,
    camera_online: true,
    sensor_online: true,
    last_seen_at: '2026-07-13T05:22:00Z',
  },
  {
    id: '00000000-0000-0000-0000-000000000103',
    code: 'LIBRARY-01',
    name: 'Library Hub',
    location_name: 'Central Library Entrance',
    status: 'ACTIVE',
    pet_capacity: 400,
    hdpe_capacity: 200,
    pet_current: 104,
    hdpe_current: 38,
    pickup_threshold_percent: 80,
    capacity_kg: 28,
    current_load_kg: 8.1,
    fill_level: 29,
    camera_online: true,
    sensor_online: true,
    last_seen_at: '2026-07-13T05:20:00Z',
  },
]

export const mockRoutes = [
  {
    id: '00000000-0000-0000-0000-000000000201',
    code: 'ROUTE-CAMPUS-013',
    vehicle_id: '00000000-0000-0000-0000-000000000301',
    status: 'IN_PROGRESS',
    threshold_percent: 70,
    total_distance_km: 12.7,
    baseline_distance_km: 18.2,
    distance_saved_percent: 30.2,
    estimated_load_kg: 42.4,
    planned_at: '2026-07-13T03:00:00Z',
    started_at: '2026-07-13T04:30:00Z',
    completed_at: null,
    stops: [
      { id: 'stop-1', hub_id: mockHubs[0].id, sequence: 1, expected_load_kg: 28.7, collected_load_kg: 28.2, collected_at: '2026-07-13T05:02:00Z' },
      { id: 'stop-2', hub_id: mockHubs[1].id, sequence: 2, expected_load_kg: 13.7, collected_load_kg: null, collected_at: null },
    ],
  },
  {
    id: '00000000-0000-0000-0000-000000000202',
    code: 'ROUTE-CAMPUS-012',
    vehicle_id: '00000000-0000-0000-0000-000000000301',
    status: 'COMPLETED',
    threshold_percent: 75,
    total_distance_km: 10.3,
    baseline_distance_km: 15.1,
    distance_saved_percent: 31.8,
    estimated_load_kg: 36.1,
    planned_at: '2026-07-12T03:00:00Z',
    started_at: '2026-07-12T04:30:00Z',
    completed_at: '2026-07-12T06:10:00Z',
    stops: [],
  },
]

export const mockDeposits = [
  { id: 'deposit-1', code: 'TRACE-PET-240713-001', material_type: 'PET', verified_material_type: 'PET', status: 'ACCEPTED', points_awarded: 10, weight_gram: 26, ai_confidence: 0.96, cleanliness_score: 0.94, created_at: '2026-07-13T05:18:00Z' },
  { id: 'deposit-2', code: 'TRACE-HDPE-240713-002', material_type: 'HDPE', verified_material_type: 'HDPE', status: 'ACCEPTED', points_awarded: 12, weight_gram: 41, ai_confidence: 0.92, cleanliness_score: 0.89, created_at: '2026-07-13T05:14:00Z' },
  { id: 'deposit-3', code: 'TRACE-PET-240713-003', material_type: 'PET', verified_material_type: 'PET', status: 'REJECTED', points_awarded: 0, weight_gram: 73, ai_confidence: 0.88, cleanliness_score: 0.32, created_at: '2026-07-13T05:09:00Z' },
]

export const mockUsers = [
  { id: 'user-1', name: 'Nguyen Minh Anh', email: 'minhanh@campus.demo', student_code: 'SV240101', role: 'USER', points_balance: 180, total_bottles_returned: 24, is_active: true },
  { id: 'user-2', name: 'Tran Gia Bao', email: 'giabao@campus.demo', student_code: 'SV240102', role: 'USER', points_balance: 95, total_bottles_returned: 13, is_active: true },
  { id: 'user-3', name: 'Le Thu Ha', email: 'thuha@campus.demo', student_code: 'SV240103', role: 'USER', points_balance: 260, total_bottles_returned: 31, is_active: true },
  { id: 'user-4', name: 'Campus Operator', email: 'operator@reloop.demo', student_code: null, role: 'OPERATOR', points_balance: 0, total_bottles_returned: 0, is_active: true },
]

export const mockVouchers = [
  { id: 'voucher-1', code: 'CANTEEN-2K', name: 'Canteen discount', partner_name: 'HCMUT Canteen', required_points: 50, value_text: '2,000 VND discount', quantity_available: 120 },
  { id: 'voucher-2', code: 'CANTEEN-5K', name: 'Canteen meal discount', partner_name: 'HCMUT Canteen', required_points: 100, value_text: '5,000 VND discount', quantity_available: 60 },
  { id: 'voucher-3', code: 'REUSABLE-BOTTLE', name: 'Reusable bottle', partner_name: 'Green Campus Club', required_points: 250, value_text: 'One reusable bottle', quantity_available: 18 },
]

const mockTrace = {
  trace_code: 'TRACE-PET-240713-001',
  current_stage: 'RECEIVED_AT_RECYCLER',
  events: [
    { stage: 'DEPOSIT_ACCEPTED', location_type: 'HUB', location_ref: 'CANTEEN-01', notes: 'Verified PET bottle accepted.', event_metadata: { confidence: 0.96 }, occurred_at: '2026-07-11T02:14:00Z' },
    { stage: 'BATCHED', location_type: 'HUB', location_ref: 'BATCH-PET-0711', notes: 'Added to campus PET batch.', event_metadata: {}, occurred_at: '2026-07-11T02:15:00Z' },
    { stage: 'PICKED_UP', location_type: 'VEHICLE', location_ref: 'TRUCK-01', notes: 'QR-confirmed pickup.', event_metadata: {}, occurred_at: '2026-07-12T04:55:00Z' },
    { stage: 'RECEIVED_AT_RECYCLER', location_type: 'FACILITY', location_ref: 'RECYCLER-DEMO-01', notes: 'Pilot receipt confirmed.', event_metadata: {}, occurred_at: '2026-07-12T07:20:00Z' },
  ],
}

export const buildMockSummary = (period = 'day') => {
  const multiplier = periodMultiplier[period] ?? 1
  const start = new Date('2026-07-13T00:00:00+07:00')
  if (period === 'week') start.setDate(start.getDate() - 6)
  if (period === 'month') start.setDate(1)
  return {
    ...baseSummary,
    period,
    period_start: start.toISOString(),
    period_end: '2026-07-14T00:00:00+07:00',
    reporting_timezone: 'Asia/Ho_Chi_Minh',
    participants: Math.round(baseSummary.participants * Math.sqrt(multiplier)),
    transactions_in_period: Math.round(baseSummary.transactions_in_period * multiplier),
    successful_transactions: Math.round(baseSummary.successful_transactions * multiplier),
    accepted_bottles: Math.round(baseSummary.accepted_bottles * multiplier),
    rejected_bottles: Math.round(baseSummary.rejected_bottles * multiplier),
    pet_bottles: Math.round(baseSummary.pet_bottles * multiplier),
    hdpe_bottles: Math.round(baseSummary.hdpe_bottles * multiplier),
    recovered_weight_kg: rounded(baseSummary.recovered_weight_kg * multiplier, 1),
    completed_routes: Math.max(1, Math.round(baseSummary.completed_routes * multiplier)),
    baseline_distance_km: rounded(baseSummary.baseline_distance_km * multiplier, 1),
    optimized_distance_km: rounded(baseSummary.optimized_distance_km * multiplier, 1),
    distance_saved_km: rounded(baseSummary.distance_saved_km * multiplier, 1),
    estimated_co2_saved_kg: rounded(baseSummary.estimated_co2_saved_kg * multiplier, 1),
  }
}

export const buildMockEsg = (period = 'day') => {
  const summary = buildMockSummary(period)
  return {
    period,
    period_start: summary.period_start,
    period_end: summary.period_end,
    reporting_timezone: summary.reporting_timezone,
    participants: summary.participants,
    total_transactions: summary.transactions_in_period,
    successful_transactions: summary.successful_transactions,
    success_rate_percent: summary.success_rate_percent,
    total_plastic_recovered_kg: summary.recovered_weight_kg,
    pet_bottles: summary.pet_bottles,
    hdpe_bottles: summary.hdpe_bottles,
    rejected_bottles: summary.rejected_bottles,
    completed_routes: summary.completed_routes,
    baseline_distance_km: summary.baseline_distance_km,
    optimized_distance_km: summary.optimized_distance_km,
    distance_saved_km: summary.distance_saved_km,
    distance_saved_percent: summary.distance_saved_percent,
    collection_efficiency_kg_per_km: summary.collection_efficiency_kg_per_km,
    vehicle_utilization_percent: summary.vehicle_utilization_percent,
    estimated_co2_saved_kg: summary.estimated_co2_saved_kg,
    traceability_completeness_percent: summary.traceability_completeness_percent,
    co2_emission_factor_kg_per_km: 0.89,
  }
}

export const getMockTelemetry = (hubId) => {
  const hub = mockHubs.find((item) => item.id === hubId) ?? mockHubs[0]
  return Array.from({ length: 8 }, (_, index) => ({
    id: `reading-${hub.id}-${index}`,
    hub_id: hub.id,
    fill_level: Math.max(0, rounded(Number(hub.fill_level) - index * 4.2, 1)),
    weight_kg: Math.max(0, rounded(Number(hub.current_load_kg) - index * 1.1, 1)),
    camera_online: true,
    sensor_online: true,
    temperature_c: 29.4,
    recorded_at: new Date(Date.parse('2026-07-13T05:23:00Z') - index * 60 * 60 * 1000).toISOString(),
  }))
}

export const getMockTraceability = (traceCode) => {
  if (traceCode.trim().toUpperCase() !== mockTrace.trace_code) {
    throw new Error('Demo trace code not found. Try TRACE-PET-240713-001.')
  }
  return structuredClone(mockTrace)
}
