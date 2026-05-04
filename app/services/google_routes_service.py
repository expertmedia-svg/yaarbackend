import re

import httpx

from app.core.config import settings


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
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY n'est pas configure.")

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

        async with httpx.AsyncClient(
            base_url=cls._base_url,
            timeout=settings.GOOGLE_ROUTES_TIMEOUT_SECONDS,
        ) as client:
            try:
                response = await client.post(
                    "/directions/v2:computeRoutes",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError("Google Routes request failed") from exc

        data = response.json()
        routes = data.get("routes")
        if not isinstance(routes, list) or not routes:
            raise RuntimeError("Google Routes response did not include any route")

        first_route = routes[0]
        if not isinstance(first_route, dict):
            raise RuntimeError("Google Routes response route format is invalid")

        distance_meters = first_route.get("distanceMeters")
        if not isinstance(distance_meters, int):
            raise RuntimeError("Google Routes response did not include distance")

        duration_minutes = cls._parse_duration_to_minutes(first_route.get("duration"))
        return distance_meters, duration_minutes