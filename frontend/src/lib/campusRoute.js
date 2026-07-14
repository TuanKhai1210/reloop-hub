const MAP_WIDTH_PX = 1200
const MAP_HEIGHT_PX = 900
const CAMPUS_WIDTH_KM = 0.92
const CAMPUS_HEIGHT_KM = 0.69

export const CAMPUS_GATES = [
  { id: 'gate-1', shortLabel: 'G1', name: 'Gate 1 - Ly Thuong Kiet Street', x: 132, y: 458 },
  { id: 'gate-2', shortLabel: 'G2', name: 'Gate 2 - To Hien Thanh Street', x: 746, y: 654 },
  { id: 'gate-3', shortLabel: 'G3', name: 'Gate 3 - To Hien Thanh Street', x: 1148, y: 630 },
]

export const CAMPUS_HUBS = [
  {
    mapId: 'H1',
    name: 'B3 Learning Hub',
    location: 'B3 - Postgraduate Study Office',
    x: 300,
    y: 340,
    fallbackFill: 68,
    fallbackLoadKg: 18.6,
  },
  {
    mapId: 'H2',
    name: 'Canteen 2 Hub',
    location: 'Canteen 2 - B4/B6 cluster',
    x: 430,
    y: 236,
    fallbackFill: 82,
    fallbackLoadKg: 28.7,
  },
  {
    mapId: 'H3',
    name: 'Canteen 3 Hub',
    location: 'Canteen 3 - C1 cluster',
    x: 927,
    y: 63,
    fallbackFill: 74,
    fallbackLoadKg: 21.4,
  },
  {
    mapId: 'H4',
    name: 'Main Library Hub',
    location: 'A2 - Main Library',
    x: 625,
    y: 474,
    fallbackFill: 45,
    fallbackLoadKg: 15.8,
  },
]

// Hand-mapped campus corridors. Intermediate nodes deliberately run around
// building footprints instead of connecting gates and Hubs with straight lines.
const ROAD_WAYPOINTS = [
  { id: 'west-entry', x: 180, y: 458 },
  { id: 'west-north', x: 180, y: 340 },
  { id: 'b3-east', x: 340, y: 340 },
  { id: 'canteen-west', x: 340, y: 236 },
  { id: 'canteen-east', x: 450, y: 236 },
  { id: 'b6-west', x: 450, y: 120 },
  { id: 'top-west', x: 450, y: 30 },
  { id: 'top-east', x: 950, y: 30 },
  { id: 'east-upper', x: 940, y: 145 },
  { id: 'east-middle', x: 940, y: 340 },
  { id: 'b9-west', x: 780, y: 340 },
  { id: 'library-east', x: 780, y: 474 },
  { id: 'bottom-middle', x: 760, y: 630 },
  { id: 'library-west', x: 560, y: 474 },
  { id: 'a5-north', x: 560, y: 330 },
  { id: 'central-north', x: 450, y: 330 },
  { id: 'south-west', x: 560, y: 580 },
  { id: 'west-lower', x: 180, y: 580 },
  { id: 'gate3-inside', x: 1120, y: 630 },
  { id: 'east-lower', x: 1120, y: 350 },
  { id: 'east-corridor', x: 1120, y: 145 },
]

const ROAD_EDGES = [
  ['gate-1', 'west-entry'],
  ['west-entry', 'west-north'],
  ['west-entry', 'west-lower'],
  ['west-north', 'H1'],
  ['H1', 'b3-east'],
  ['H1', 'central-north'],
  ['b3-east', 'canteen-west'],
  ['canteen-west', 'H2'],
  ['H2', 'canteen-east'],
  ['canteen-east', 'b6-west'],
  ['b6-west', 'top-west'],
  ['canteen-east', 'a5-north'],
  ['top-west', 'top-east'],
  ['top-east', 'H3'],
  ['H3', 'east-upper'],
  ['east-upper', 'east-middle'],
  ['east-upper', 'east-corridor'],
  ['east-middle', 'b9-west'],
  ['b9-west', 'library-east'],
  ['library-east', 'H4'],
  ['library-east', 'bottom-middle'],
  ['H4', 'library-west'],
  ['library-west', 'a5-north'],
  ['library-west', 'south-west'],
  ['a5-north', 'central-north'],
  ['central-north', 'b3-east'],
  ['south-west', 'west-lower'],
  ['bottom-middle', 'gate-2'],
  ['gate3-inside', 'gate-3'],
  ['gate3-inside', 'east-lower'],
  ['east-lower', 'east-corridor'],
]

const ROAD_NODES = new Map([
  ...CAMPUS_GATES.map((gate) => [gate.id, gate]),
  ...CAMPUS_HUBS.map((hub) => [hub.mapId, { ...hub, id: hub.mapId }]),
  ...ROAD_WAYPOINTS.map((point) => [point.id, point]),
])

const permutations = (items) => {
  if (items.length <= 1) return [items]
  return items.flatMap((item, index) => {
    const remaining = [...items.slice(0, index), ...items.slice(index + 1)]
    return permutations(remaining).map((permutation) => [item, ...permutation])
  })
}

export const campusDistanceKm = (a, b) => {
  const dxKm = ((a.x - b.x) / MAP_WIDTH_PX) * CAMPUS_WIDTH_KM
  const dyKm = ((a.y - b.y) / MAP_HEIGHT_PX) * CAMPUS_HEIGHT_KM
  return Math.hypot(dxKm, dyKm)
}

const roadAdjacency = (() => {
  const adjacency = new Map([...ROAD_NODES.keys()].map((id) => [id, []]))
  for (const [fromId, toId] of ROAD_EDGES) {
    const from = ROAD_NODES.get(fromId)
    const to = ROAD_NODES.get(toId)
    const distanceKm = campusDistanceKm(from, to)
    adjacency.get(fromId).push({ id: toId, distanceKm })
    adjacency.get(toId).push({ id: fromId, distanceKm })
  }
  return adjacency
})()

const graphId = (point) => point.mapId || point.id

export const shortestRoadLeg = (from, to) => {
  const fromId = graphId(from)
  const toId = graphId(to)
  const distances = new Map([...ROAD_NODES.keys()].map((id) => [id, Number.POSITIVE_INFINITY]))
  const previous = new Map()
  const unvisited = new Set(ROAD_NODES.keys())
  distances.set(fromId, 0)

  while (unvisited.size) {
    let currentId = null
    let currentDistance = Number.POSITIVE_INFINITY
    for (const id of unvisited) {
      if (distances.get(id) < currentDistance) {
        currentId = id
        currentDistance = distances.get(id)
      }
    }
    if (currentId === null || currentId === toId) break
    unvisited.delete(currentId)
    for (const edge of roadAdjacency.get(currentId) || []) {
      if (!unvisited.has(edge.id)) continue
      const candidateDistance = currentDistance + edge.distanceKm
      if (candidateDistance < distances.get(edge.id)) {
        distances.set(edge.id, candidateDistance)
        previous.set(edge.id, currentId)
      }
    }
  }

  const pathIds = [toId]
  while (pathIds[0] !== fromId) {
    const parentId = previous.get(pathIds[0])
    if (!parentId) throw new Error(`No mapped campus path between ${fromId} and ${toId}.`)
    pathIds.unshift(parentId)
  }

  return {
    distanceKm: distances.get(toId),
    points: pathIds.map((id) => ROAD_NODES.get(id)),
  }
}

export const routeDistanceKm = (gate, stops) => {
  if (!stops.length) return 0
  const points = [gate, ...stops, gate]
  return points.slice(1).reduce(
    (total, point, index) => total + shortestRoadLeg(points[index], point).distanceKm,
    0,
  )
}

const mappedRoutePoints = (gate, stops) => {
  if (!stops.length) return [gate]
  const destinations = [gate, ...stops, gate]
  return destinations.slice(1).reduce((points, destination, index) => {
    const leg = shortestRoadLeg(destinations[index], destination).points
    return [...points, ...leg.slice(index === 0 ? 0 : 1)]
  }, [])
}

export const hydrateCampusHubs = (liveHubs = []) => CAMPUS_HUBS.map((hub, index) => {
  const liveHub = liveHubs[index]
  return {
    ...hub,
    id: liveHub?.id || hub.mapId,
    code: liveHub?.code || `CAMPUS-${hub.mapId}`,
    fillLevel: Number(liveHub?.fill_level ?? hub.fallbackFill),
    expectedLoadKg: Number(liveHub?.current_load_kg ?? hub.fallbackLoadKg),
    status: liveHub?.status || (hub.fallbackFill >= 80 ? 'NEAR_FULL' : 'ACTIVE'),
  }
})

export const optimizeCampusRoute = ({ gateId, hubs }) => {
  const gate = CAMPUS_GATES.find((item) => item.id === gateId) || CAMPUS_GATES[0]
  const candidates = permutations(hubs)
  const bestStops = candidates.reduce((best, candidate) => (
    routeDistanceKm(gate, candidate) < routeDistanceKm(gate, best) ? candidate : best
  ), candidates[0] || [])
  const baselineStops = [...hubs]
  const distanceKm = routeDistanceKm(gate, bestStops)
  const baselineDistanceKm = routeDistanceKm(gate, baselineStops)
  const savedPercent = baselineDistanceKm > 0
    ? Math.max(0, ((baselineDistanceKm - distanceKm) / baselineDistanceKm) * 100)
    : 0
  const estimatedLoadKg = bestStops.reduce((total, hub) => total + hub.expectedLoadKg, 0)
  const estimatedMinutes = distanceKm > 0
    ? Math.ceil((distanceKm / 12) * 60 + bestStops.length * 3)
    : 0

  return {
    gate,
    stops: bestStops,
    points: mappedRoutePoints(gate, bestStops),
    distanceKm,
    baselineDistanceKm,
    savedPercent,
    estimatedLoadKg,
    estimatedMinutes,
  }
}

export const routePath = (points) => points
  .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
  .join(' ')

export const pointPosition = (point) => ({
  left: `${(point.x / MAP_WIDTH_PX) * 100}%`,
  top: `${(point.y / MAP_HEIGHT_PX) * 100}%`,
})
