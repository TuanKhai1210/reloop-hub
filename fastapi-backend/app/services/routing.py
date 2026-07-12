from math import asin, cos, radians, sin, sqrt

from app.models import Hub, Vehicle


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))


def optimize_nearest_neighbor(vehicle: Vehicle, hubs: list[Hub]) -> tuple[list[tuple[Hub, float]], float, float, float]:
    """Capacity-aware nearest-neighbour DVRP heuristic.

    Returns ordered (hub, distance from previous), optimized distance including
    return to depot, fixed-schedule baseline, and estimated load.
    """
    remaining = list(hubs)
    current_lat, current_lon = vehicle.latitude, vehicle.longitude
    ordered: list[tuple[Hub, float]] = []
    load = 0.0
    total = 0.0

    while remaining:
        feasible = [hub for hub in remaining if load + hub.current_load_kg <= vehicle.capacity_kg]
        if not feasible:
            break
        nearest = min(
            feasible,
            key=lambda hub: haversine_km(current_lat, current_lon, hub.latitude, hub.longitude),
        )
        leg = haversine_km(current_lat, current_lon, nearest.latitude, nearest.longitude)
        ordered.append((nearest, leg))
        total += leg
        load += nearest.current_load_kg
        current_lat, current_lon = nearest.latitude, nearest.longitude
        remaining.remove(nearest)

    if ordered:
        total += haversine_km(current_lat, current_lon, vehicle.latitude, vehicle.longitude)

    baseline = sum(
        2 * haversine_km(vehicle.latitude, vehicle.longitude, hub.latitude, hub.longitude)
        for hub, _ in ordered
    )
    return ordered, round(total, 3), round(baseline, 3), round(load, 3)

