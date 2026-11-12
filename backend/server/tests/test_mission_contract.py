"""HTTP boundary cases for the public mission endpoint, without terrain scans."""
import json
from unittest.mock import patch

from django.test import SimpleTestCase


class MissionRequestContractTests(SimpleTestCase):
    url = "/api/mission/"
    payload = {
        "latitude": -85,
        "longitude": 30,
        "launch_date": "2026-05-29T12:00:00Z",
        "landing_date": "2026-06-01T12:00:00Z",
    }

    def setUp(self):
        simulation = patch("server.mission.views.calculate_mission")
        self.simulate = simulation.start()
        self.addCleanup(simulation.stop)
        search = patch("server.mission.views.find_safe_haven")
        self.search = search.start()
        self.addCleanup(search.stop)
        profile = patch("server.mission.views.calculate_horizon_profile", return_value=[0.0] * 360)
        self.profile = profile.start()
        self.addCleanup(profile.stop)

    def assert_rejected(self, body, message, content_type="application/json"):
        response = self.client.generic(
            "POST", self.url, body, content_type=content_type, CONTENT_TYPE=content_type,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": message})
        self.simulate.assert_not_called()
        self.search.assert_not_called()
        self.profile.assert_not_called()

    def test_non_post_methods_do_not_run_simulation(self):
        for method in ("GET", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                response = self.client.generic(method, self.url)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "POST")
        self.simulate.assert_not_called()
        self.search.assert_not_called()

    def test_wrong_content_types_are_rejected(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "text/html"):
            with self.subTest(content_type=content_type):
                self.assert_rejected(json.dumps(self.payload), "Ожидается application/json", content_type)

    def test_malformed_json_and_invalid_utf8_are_rejected(self):
        for body in (b"", b"{", b'{"latitude": -85,}', b"\xff"):
            with self.subTest(body=body):
                self.assert_rejected(body, "Некорректный JSON")

    def test_json_scalars_and_arrays_are_rejected(self):
        for value in (None, True, 42, "mission", [], [self.payload]):
            with self.subTest(value=value):
                self.assert_rejected(json.dumps(value), "Ожидается JSON-объект")

    def test_missing_required_fields_are_rejected_before_calculation(self):
        errors = {
            "latitude": "Посадка разрешена только на Южном полюсе Луны",
            "longitude": "Долгота должна быть числом от -180 до 180",
            "launch_date": "launch_date должна быть датой ISO 8601 с часовым поясом",
            "landing_date": "landing_date должна быть датой ISO 8601 с часовым поясом",
        }
        for field, message in errors.items():
            with self.subTest(field=field):
                body = {key: value for key, value in self.payload.items() if key != field}
                self.assert_rejected(json.dumps(body), message)

    def test_nonfinite_and_wrong_type_coordinates_are_rejected(self):
        errors = {
            "latitude": "Посадка разрешена только на Южном полюсе Луны",
            "longitude": "Долгота должна быть числом от -180 до 180",
        }
        for field, message in errors.items():
            for value in (True, False, None, "-85", [], {}, float("nan"), float("inf"), -float("inf")):
                with self.subTest(field=field, value=value):
                    self.assert_rejected(json.dumps({**self.payload, field: value}), message)

    def test_out_of_range_coordinates_are_rejected(self):
        for field, values, message in (
            ("latitude", (-90.0001, -59.9999), "Посадка разрешена только на Южном полюсе Луны"),
            ("longitude", (-180.0001, 180.0001), "Долгота должна быть числом от -180 до 180"),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assert_rejected(json.dumps({**self.payload, field: value}), message)

    def test_invalid_calendar_dates_and_date_types_are_rejected(self):
        for field in ("launch_date", "landing_date"):
            for value in ("2026-02-30T12:00:00Z", "2026-13-01T12:00:00Z",
                          "2026-06-01T25:00:00Z", "2026-06-01", "2026-06-01T12:00:00",
                          "", True, 0, [], {}):
                with self.subTest(field=field, value=value):
                    self.assert_rejected(
                        json.dumps({**self.payload, field: value}),
                        f"{field} должна быть датой ISO 8601 с часовым поясом",
                    )

    def test_coordinate_boundaries_and_json_charset_are_accepted(self):
        self.simulate.return_value = {"status": "SUCCESS"}
        self.search.return_value = {"status": "NOT_NEEDED"}
        for latitude in (-90, -60):
            for longitude in (-180, 180):
                with self.subTest(latitude=latitude, longitude=longitude):
                    payload = {**self.payload, "latitude": latitude, "longitude": longitude}
                    response = self.client.generic(
                        "POST", self.url, json.dumps(payload),
                        content_type="application/json; charset=utf-8",
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {
                        "latitude": latitude, "longitude": longitude,
                        "transit": {**{key: self.payload[key] for key in ("launch_date", "landing_date")},
                                    "transit_hours": 72.0},
                        "surface": {"status": "SUCCESS", "safe_haven": {"status": "NOT_NEEDED"},
                                    "horizon_profile": [0.0] * 360},
                    })
                    args = self.simulate.call_args.args
                    self.assertEqual(args[:2], (latitude, longitude))
                    self.assertIsNotNone(args[2].utcoffset())
                    self.assertEqual(self.search.call_args.args[:3], args)
                    self.assertEqual(self.search.call_args.args[3]["status"], "SUCCESS")

    def test_failed_forecast_is_a_successful_http_response(self):
        self.simulate.return_value = {"status": "FAIL", "failure_reasons": ["LOW_BATTERY"]}
        self.search.return_value = {"status": "NOT_FOUND", "destination": None}
        response = self.client.post(self.url, self.payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["surface"]["status"], "FAIL")
        self.assertEqual(response.json()["surface"]["failure_reasons"], ["LOW_BATTERY"])
        self.assertEqual(response.json()["surface"]["safe_haven"], self.search.return_value)
        self.simulate.assert_called_once()
        self.search.assert_called_once()
