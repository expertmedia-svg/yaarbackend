import math
import re
import httpx

from app.core.config import settings


def _haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


class GoogleRoutesService:
    _base_url = "https://routes.googleapis.com"
    _field_mask = "routes.distanceMeters,routes.duration"

    @staticmethod
    def _parse_duration_to_minutes(raw_duration: str | None) -> int:
        if not raw_duration:
            raise RuntimeError("Google Routes response did not include duration")

        match = re.fullmatch(r"(?P<seconds>\d+(?:\.\d+)?)s", raw_duration.strip())
        if match is None:
            raise RuntimeError("Unexpected Google Routes duration format")

        seconds = float(match.group("seconds"))
        minutes = int((seconds + 59) // 60)
        return max(minutes, 1)

    @classmethod
    async def compute_driving_metrics(
        cls,
        *,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> tuple[int, int]:
        api_key = settings.GOOGLE_MAPS_API_KEY
        if api_key:
            payload = {
                "origin": {
                    "location": {
                        "latLng": {"latitude": origin_lat, "longitude": origin_lng}
                    }
                },
                "destination": {
                    "location": {
                        "latLng": {
                            "latitude": destination_lat,
                            "longitude": destination_lng,
                        }
                    }
                },
                "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE",
                "computeAlternativeRoutes": False,
                "languageCode": "fr-FR",
                "units": "METRIC",
            }

            headers = {
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": cls._field_mask,
            }

            try:
                async with httpx.AsyncClient(
                    base_url=cls._base_url,
                    timeout=settings.GOOGLE_ROUTES_TIMEOUT_SECONDS,
                ) as client:
                    response = await client.post(
                        "/directions/v2:computeRoutes",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        routes = data.get("routes")
                        if isinstance(routes, list) and routes:
                            first_route = routes[0]
                            dist = first_route.get("distanceMeters")
                            if isinstance(dist, int):
                                dur = cls._parse_duration_to_minutes(first_route.get("duration"))
                                return dist, dur
            except Exception:
                pass

        # Fallback 1: Free OpenStreetMap OSRM routing
        try:
            osrm_url = (
                f"http://router.project-osrm.org/route/v1/driving/"
                f"{origin_lng},{origin_lat};{destination_lng},{destination_lat}?overview=false"
            )
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(osrm_url, headers={"User-Agent": "YaarBackend/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    routes = data.get("routes")
                    if isinstance(routes, list) and routes:
                        r = routes[0]
                        dist_m = int(round(r.get("distance", 0)))
                        dur_s = float(r.get("duration", 0))
                        dur_m = max(int(round((dur_s + 59) // 60)), 1)
                        if dist_m > 0:
                            return dist_m, dur_m
        except Exception:
            pass

        # Fallback 2: Realistic road detour calculation (1.30x straight line, 24 km/h speed)
        straight_meters = _haversine_distance_meters(
            origin_lat, origin_lng, destination_lat, destination_lng
        )
        road_meters = max(int(round(straight_meters * 1.30)), 10)
        speed_kmh = 24.0
        minutes = max(int(round((road_meters / 1000.0) / speed_kmh * 60.0)), 1)
        return road_meters, minutes