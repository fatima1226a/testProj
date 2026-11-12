"""Real geometry and HTTP contracts used by the frontend horizon plot."""
import math
from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import SimpleTestCase
from server.mission import views


class MissionFrontendTests(SimpleTestCase):
    payload = {"latitude": -85, "longitude": 30,
               "launch_date": "2026-05-29T12:00:00Z",
               "landing_date": "2026-06-01T12:00:00Z"}

    def test_solar_azimuth_uses_north_clockwise_cardinal_directions(self):
        for longitude, expected in ((0, 0), (90, 270), (180, 180), (-90, 90)):
            with self.subTest(longitude=longitude):
                self.assertAlmostEqual(views.calculate_conditions(
                    -60, longitude, views.MODEL_EPOCH)["sun_azimuth_deg"], expected, places=4)

    def test_earth_azimuth_uses_north_clockwise_cardinal_directions(self):
        # At the model epoch the synthetic Earth subpoint longitude is +6 degrees.
        for longitude, expected in ((6, 0), (96, 270), (-174, 180), (-84, 90)):
            with self.subTest(longitude=longitude):
                self.assertAlmostEqual(views.calculate_dte(
                    -60, longitude, views.MODEL_EPOCH)["earth_azimuth_deg"], expected, places=4)

    def test_azimuth_wrap_and_vertical_convention(self):
        self.assertEqual(views._azimuth_degrees(0, 0), 0)
        for east, north in ((-1e-8, 1), (1, 0), (-1, 0), (0, -1)):
            value = views._azimuth_degrees(east, north)
            self.assertGreaterEqual(value, 0)
            self.assertLess(value, 360)

    def test_profile_samples_local_north_then_east_without_duplicate_endpoint(self):
        longitude = 30
        with patch.object(views, "_local_horizon", return_value=math.radians(12.5)) as horizon:
            profile = views.calculate_horizon_profile(-85, longitude)
        self.assertEqual(profile, [12.5] * 360)
        self.assertEqual(horizon.call_count, 360)
        north, east = horizon.call_args_list[0].args, horizon.call_args_list[90].args
        lon = math.radians(longitude)
        self.assertAlmostEqual(north[2], math.cos(lon))
        self.assertAlmostEqual(north[3], math.sin(lon))
        self.assertAlmostEqual(east[2], -math.sin(lon))
        self.assertAlmostEqual(east[3], math.cos(lon))

    def test_api_returns_real_profile_and_hourly_azimuths(self):
        response = self.client.post("/api/mission/", self.payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        surface = response.json()["surface"]
        profile = surface["horizon_profile"]
        self.assertEqual(len(profile), 360)
        self.assertTrue(all(math.isfinite(value) and 0 <= value <= 90 for value in profile))
        x, y = views._polar_position(-85, 30)
        for azimuth in (0, 90, 180, 270):
            direction = math.radians(30 + azimuth)
            self.assertAlmostEqual(profile[azimuth], math.degrees(views._local_horizon(
                x, y, math.cos(direction), math.sin(direction))), places=4)
        start = datetime.fromisoformat(self.payload["landing_date"].replace("Z", "+00:00"))
        rows = surface["forecast"]["timeline"]
        self.assertEqual(len(rows), 168)
        for hour, row in enumerate(rows):
            timestamp = start + timedelta(hours=hour)
            self.assertEqual(row["sun_azimuth_deg"], views.calculate_conditions(-85, 30, timestamp)["sun_azimuth_deg"])
            self.assertEqual(row["earth_azimuth_deg"], views.calculate_dte(-85, 30, timestamp)["earth_azimuth_deg"])
            for field in ("sun_azimuth_deg", "earth_azimuth_deg"):
                self.assertTrue(math.isfinite(row[field]) and 0 <= row[field] < 360)
                self.assertEqual(surface["forecast"]["units"][field], "deg")
        self.assertEqual(surface["sun_azimuth_deg"], rows[0]["sun_azimuth_deg"])
        self.assertEqual(surface["earth_azimuth_deg"], rows[0]["earth_azimuth_deg"])

    def test_openapi_describes_frontend_response_fields(self):
        schema = self.client.get("/api/schema/").json()
        response = schema["paths"]["/api/mission/"]["post"]["responses"]["200"]
        self.assertEqual(response["content"]["application/json"]["schema"]["$ref"],
                         "#/components/schemas/MissionResponse")
        fields = schema["components"]["schemas"]["MissionResponse"]["properties"]["surface"]["properties"]
        self.assertEqual(fields["horizon_profile"]["minItems"], 360)
        self.assertEqual(fields["horizon_profile"]["maxItems"], 360)
        self.assertEqual(set(fields["forecast"]["properties"]["timeline"]["items"]["required"]),
                         {"sun_azimuth_deg", "earth_azimuth_deg"})
