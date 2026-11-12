import math
from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase

from .views import (
    MODEL_EPOCH, MOON_RADIUS_M, calculate_conditions, calculate_dte,
    calculate_dust, calculate_landing_zone, calculate_mission, calculate_power,
    calculate_radiation, find_safe_haven,
    calculate_signal_latency, calculate_thermal_shock,
)


class MissionTests(SimpleTestCase):
    payload = {
        "latitude": -85.0,
        "longitude": 30.0,
        "timestamp": "2026-06-01T12:00:00Z",
    }

    def test_response_and_validation(self):
        response = self.client.post("/api/mission/", self.payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key, value in self.payload.items():
            self.assertEqual(data[key], value)
        self.assertEqual(data["model"], "synthetic-v1")
        self.assertIn(data["status"], ("SUCCESS", "FAIL"))
        self.assertEqual(len(data["forecast"]["timeline"]), 24)
        self.assertIn("power", data)
        self.assertIn("windows", data["dte"])
        self.assertIn("samples", data["landing_zone"])
        self.assertTrue(data["metadata"]["is_simulation"])
        self.assertIn("dust", data)
        self.assertIn("radiation", data)
        self.assertIn("safe_haven", data)
        self.assertIn("thermal_shock", data)
        self.assertIn("signal_latency", data)
        for latitude in (-90, -60):
            self.assertEqual(self.client.post(
                "/api/mission/", {**self.payload, "latitude": latitude},
                content_type="application/json",
            ).status_code, 200)
        for latitude in (-90.01, -59.99, True, "-85", None, float("nan")):
            response = self.client.post(
                "/api/mission/", {**self.payload, "latitude": latitude},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"],
                             "Посадка разрешена только на Южном полюсе Луны")
        self.assertEqual(self.client.post(
            "/api/mission/", "{", content_type="application/json",
        ).status_code, 400)
        self.assertEqual(self.client.get("/api/mission/").status_code, 405)

    @patch("server.mission.views._elevation", return_value=0.0)
    def test_flat_surface_light_and_dark(self, elevation):
        light = calculate_conditions(-60, 0, MODEL_EPOCH)
        dark = calculate_conditions(-60, 180, MODEL_EPOCH)
        self.assertEqual(light["slope_deg"], 0)
        self.assertAlmostEqual(light["insolation_percent"], 50, places=2)
        self.assertFalse(light["is_shadowed"])
        self.assertEqual(dark["insolation_percent"], 0)
        self.assertTrue(dark["is_shadowed"])
        self.assertEqual(dark["temperature_c"], -223.15)
        self.assertGreater(light["temperature_c"], dark["temperature_c"])

    def test_time_dependence_and_bounds(self):
        results = [calculate_conditions(-85, 30, MODEL_EPOCH + timedelta(days=day))
                   for day in range(60)]
        self.assertGreater(len({r["temperature_c"] for r in results}), 1)
        self.assertTrue(any(r["is_shadowed"] for r in results))
        self.assertTrue(any(not r["is_shadowed"] for r in results))
        self.assertEqual(len({r["elevation_m"] for r in results}), 1)
        for result in results:
            self.assertTrue(0 <= result["insolation_percent"] <= 100)
            self.assertTrue(0 <= result["slope_deg"] < 90)
            self.assertTrue(-223.15 <= result["temperature_c"] <= 116.85)
            self.assertTrue(math.isfinite(result["elevation_m"]))

    def test_slope_from_known_gradient(self):
        with patch("server.mission.views._elevation", side_effect=lambda x, y: 0.25 * x):
            result = calculate_conditions(-85, 0, MODEL_EPOCH)
        self.assertAlmostEqual(result["slope_deg"], math.degrees(math.atan(0.25)), places=2)

    def test_terrain_blocks_sun_above_horizon(self):
        site_x = MOON_RADIUS_M * math.radians(5)
        with patch("server.mission.views._elevation", return_value=0.0):
            clear = calculate_conditions(-85, 0, MODEL_EPOCH)
        with patch("server.mission.views._elevation",
                   side_effect=lambda x, y: 1_000.0 if x > site_x + 200 else 0.0):
            blocked = calculate_conditions(-85, 0, MODEL_EPOCH)
        self.assertGreater(clear["insolation_percent"], 0)
        self.assertGreater(blocked["sun_elevation_deg"], 0)
        self.assertTrue(blocked["is_shadowed"])
        self.assertEqual(blocked["insolation_percent"], 0)
        self.assertLess(blocked["temperature_c"], clear["temperature_c"])

    def test_timezone_equivalence(self):
        response = self.client.post(
            "/api/mission/", {**self.payload, "timestamp": "2026-06-01T18:00:00+06:00"},
            content_type="application/json",
        )
        baseline = self.client.post("/api/mission/", self.payload, content_type="application/json")
        self.assertEqual(response.json()["temperature_c"], baseline.json()["temperature_c"])
        self.assertEqual(response.json()["insolation_percent"], baseline.json()["insolation_percent"])
        for key in ("status", "power", "dte", "forecast", "landing_zone", "summary",
                    "dust", "radiation", "safe_haven", "thermal_shock", "signal_latency"):
            self.assertEqual(response.json()[key], baseline.json()[key])


class MissionForecastTests(SimpleTestCase):
    light = {"insolation_percent": 100.0, "is_shadowed": False,
             "slope_deg": 0.0, "temperature_c": 116.85}
    shadow = {"insolation_percent": 0.0, "is_shadowed": True,
              "slope_deg": 0.0, "temperature_c": -223.15}

    def forecast(self, conditions):
        with patch("server.mission.views.calculate_conditions", return_value=conditions):
            return calculate_mission(-85, 30, MODEL_EPOCH)

    def test_panel_output_and_shadow_heating(self):
        partial = calculate_power({**self.light, "insolation_percent": 25.0}, 1_000)
        self.assertEqual(partial["generation_w"], 50)
        self.assertEqual(partial["consumption_w"], 30)
        self.assertEqual(partial["energy_wh"], 1_020)
        dark = calculate_power(self.shadow, 1_000)
        self.assertEqual(dark["generation_w"], 0)
        self.assertEqual(dark["heater_w"], 50)
        self.assertEqual(dark["energy_wh"], 920)

    def test_battery_limits_and_unserved_energy(self):
        full = calculate_power(self.light, 1_990)
        self.assertEqual(full["energy_wh"], 2_000)
        self.assertEqual(full["battery_soc_percent"], 100)
        self.assertEqual(full["curtailed_energy_wh"], 160)
        empty = calculate_power(self.shadow, 20)
        self.assertEqual(empty["energy_wh"], 0)
        self.assertEqual(empty["unserved_energy_wh"], 60)

    def test_energy_balance_and_success(self):
        result = self.forecast(self.light)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["failure_reasons"], [])
        power = result["power"]
        self.assertEqual(power["final_soc_percent"], 100)
        self.assertEqual(power["clean_generated_energy_wh"], 200 * 24)
        self.assertLess(power["generated_energy_wh"], power["clean_generated_energy_wh"])
        self.assertAlmostEqual(power["generated_energy_wh"] + power["dust_loss_energy_wh"],
                               power["clean_generated_energy_wh"], places=3)
        self.assertEqual(power["consumed_energy_wh"], 30 * 24)
        self.assertAlmostEqual(
            2_000 + power["generated_energy_wh"] - power["consumed_energy_wh"]
            + power["unserved_energy_wh"] - power["curtailed_energy_wh"],
            power["final_energy_wh"],
        )

    def test_long_shadow_fails_and_recovery_does_not_erase_failure(self):
        result = self.forecast(self.shadow)
        self.assertEqual(result["power"]["final_energy_wh"], 80)
        self.assertEqual(result["power"]["final_soc_percent"], 4)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("LOW_BATTERY", result["failure_reasons"])
        samples = [self.shadow] * 21 + [self.light] * 3
        with patch("server.mission.views.calculate_conditions", side_effect=samples):
            recovered = calculate_mission(-85, 30, MODEL_EPOCH)
        self.assertGreater(recovered["power"]["final_soc_percent"], 20)
        self.assertIn("LOW_BATTERY", recovered["failure_reasons"])

    def test_slope_threshold_and_multiple_failure_reasons(self):
        self.assertEqual(self.forecast({**self.light, "slope_deg": 15})["status"], "SUCCESS")
        unsafe = self.forecast({**self.light, "slope_deg": 15.01})
        self.assertEqual(unsafe["failure_reasons"], ["UNSAFE_SLOPE"])
        with patch("server.mission.views.INITIAL_SOC_PERCENT", 0):
            empty = self.forecast({**self.shadow, "slope_deg": 16})
        self.assertEqual(empty["failure_reasons"],
                         ["UNSAFE_SLOPE", "LOW_BATTERY", "POWER_SHORTFALL"])

    def test_slope_just_above_threshold_is_not_rounded_safe(self):
        gradient = math.tan(math.radians(15.001))
        with patch("server.mission.views._elevation", side_effect=lambda x, y: gradient * x):
            result = calculate_mission(-85, 30, MODEL_EPOCH)
        self.assertGreater(result["slope_deg"], 15)
        self.assertIn("UNSAFE_SLOPE", result["failure_reasons"])

    def test_minimum_soc_includes_initial_state_and_equality_is_safe(self):
        with patch("server.mission.views.INITIAL_SOC_PERCENT", 20):
            self.assertEqual(self.forecast(self.light)["status"], "SUCCESS")
        with patch("server.mission.views.INITIAL_SOC_PERCENT", 19):
            self.assertIn("LOW_BATTERY", self.forecast(self.light)["failure_reasons"])

    @patch("server.mission.views._elevation", return_value=0.0)
    def test_dte_near_side_far_side_and_change_with_time(self, elevation):
        self.assertTrue(calculate_dte(-60, 0, MODEL_EPOCH)["visible"])
        self.assertFalse(calculate_dte(-60, 180, MODEL_EPOCH)["visible"])
        states = {calculate_dte(-85, 0, MODEL_EPOCH + timedelta(days=d))["visible"]
                  for d in range(28)}
        self.assertEqual(states, {True, False})

    def test_dte_terrain_obstruction(self):
        with patch("server.mission.views._local_horizon", return_value=math.radians(40)):
            self.assertFalse(calculate_dte(-60, 0, MODEL_EPOCH)["visible"])

    def test_dte_window_merging_and_forecast_clipping(self):
        states = [True] * 2 + [False] * 3 + [True] * 4 + [False] * 14 + [True]
        with patch("server.mission.views.calculate_dte", side_effect=[
            {"visible": state, "earth_elevation_deg": 10 if state else -10} for state in states
        ]):
            result = self.forecast(self.light)
        self.assertEqual(result["dte"]["available_hours"], 7)
        self.assertEqual(result["dte"]["windows"], [
            {"start": "2026-01-01T00:00:00Z", "end": "2026-01-01T02:00:00Z"},
            {"start": "2026-01-01T05:00:00Z", "end": "2026-01-01T09:00:00Z"},
            {"start": "2026-01-01T23:00:00Z", "end": "2026-01-02T00:00:00Z"},
        ])
        self.assertEqual(result["forecast"]["timeline"][-1]["end"], result["forecast"]["end"])

    def test_dte_always_visible_or_unavailable(self):
        for visible in (True, False):
            with self.subTest(visible=visible), patch(
                "server.mission.views.calculate_dte",
                return_value={"visible": visible, "earth_elevation_deg": 10 if visible else -10},
            ):
                result = self.forecast(self.light)
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["dte"]["available_hours"], 24 if visible else 0)
            self.assertEqual(len(result["dte"]["windows"]), 1 if visible else 0)

    def test_forecast_timestamp_overflow_is_bad_request(self):
        response = self.client.post("/api/mission/", {
            "latitude": -85, "longitude": 30, "timestamp": "9999-12-31T12:00:00Z",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_longitude_and_timestamp_remain_bad_requests(self):
        base = {"latitude": -85, "longitude": 30, "timestamp": "2026-06-01T12:00:00Z"}
        for changes in ({"longitude": 181}, {"longitude": True}, {"longitude": float("inf")},
                        {"timestamp": "bad"}, {"timestamp": "2026-06-01T12:00:00"},
                        {"timestamp": None}):
            with self.subTest(changes=changes):
                response = self.client.post("/api/mission/", {**base, **changes},
                                            content_type="application/json")
                self.assertEqual(response.status_code, 400)


class LandingZoneTests(SimpleTestCase):
    @patch("server.mission.views._elevation", return_value=123.0)
    def test_flat_disk_is_safe_with_boundary_and_unique_samples(self, elevation):
        zone = calculate_landing_zone(-85, 30)
        self.assertTrue(zone["is_safe"])
        self.assertEqual(zone["safe_radius_estimate_m"], 100)
        self.assertEqual(zone["unsafe_sample_count"], 0)
        self.assertEqual(zone["slope_stddev_deg"], 0)
        self.assertEqual(zone["elevation_range_m"], 0)
        samples = zone["samples"]
        offsets = {(s["east_m"], s["north_m"]) for s in samples}
        self.assertEqual(len(offsets), zone["sample_count"])
        self.assertIn((0, 0), offsets)
        self.assertGreaterEqual(sum(s["distance_m"] == 100 for s in samples), 32)
        for sample in samples:
            self.assertLessEqual(sample["distance_m"], 100)
            self.assertAlmostEqual(sample["distance_m"],
                                   math.hypot(sample["east_m"], sample["north_m"]), places=5)

    def test_unsafe_neighbours_reduce_radius_and_fail_mission(self):
        centre_x = MOON_RADIUS_M * math.radians(5)
        coefficient = math.tan(math.radians(15)) / 180
        with patch("server.mission.views._elevation", side_effect=lambda x, y:
                   coefficient * ((x - centre_x) ** 2 + y ** 2)):
            zone = calculate_landing_zone(-85, 0)
            result = calculate_mission(-85, 0, MODEL_EPOCH)
        self.assertTrue(zone["samples"][0]["safe"])
        self.assertLess(result["slope_deg"], 15)
        self.assertFalse(zone["is_safe"])
        self.assertEqual(zone["safe_radius_estimate_m"], 75)
        self.assertGreater(zone["max_slope_deg"], 15)
        self.assertGreater(zone["slope_stddev_deg"], 0)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("UNSAFE_LANDING_ZONE", result["failure_reasons"])

    def test_unsafe_centre_has_zero_safe_radius(self):
        with patch("server.mission.views._elevation", side_effect=lambda x, y: x):
            zone = calculate_landing_zone(-85, 0)
        self.assertFalse(zone["is_safe"])
        self.assertEqual(zone["safe_radius_estimate_m"], 0)
        self.assertEqual(zone["unsafe_sample_count"], zone["sample_count"])

    @patch("server.mission.views._elevation", return_value=0.0)
    def test_pole_and_longitude_wrap_are_finite_and_geographically_correct(self, elevation):
        for latitude, longitude in ((-90, 0), (-90, 180), (-85, 180), (-85, -180)):
            with self.subTest(latitude=latitude, longitude=longitude):
                zone = calculate_landing_zone(latitude, longitude)
                self.assertTrue(zone["is_safe"])
                for sample in zone["samples"]:
                    self.assertTrue(-90 <= sample["latitude"] <= -60)
                    self.assertTrue(-180 <= sample["longitude"] <= 180)
                    lat1, lat2 = map(math.radians, (latitude, sample["latitude"]))
                    dlon = math.radians(sample["longitude"] - longitude)
                    haversine = (math.sin((lat2 - lat1) / 2) ** 2
                                 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
                    distance = 2 * MOON_RADIUS_M * math.asin(math.sqrt(haversine))
                    self.assertAlmostEqual(distance, sample["distance_m"], places=5)

    @patch("server.mission.views._elevation", return_value=0.0)
    def test_neighbours_outside_permitted_region_are_unsafe(self, elevation):
        zone = calculate_landing_zone(-60, 0)
        self.assertFalse(zone["is_safe"])
        self.assertEqual(zone["safe_radius_estimate_m"], 0)
        self.assertTrue(any(not s["within_allowed_region"] for s in zone["samples"]))


class AnalyticsPackageTests(SimpleTestCase):
    def test_hourly_chart_contract_summary_and_energy_continuity(self):
        response = self.client.post("/api/mission/", MissionTests.payload,
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        forecast, power, summary = data["forecast"], data["power"], data["summary"]
        rows = forecast["timeline"]
        self.assertEqual(len(rows), 24)
        self.assertEqual(forecast["step_h"], 1)
        self.assertEqual(forecast["duration_h"], 24)
        energy, soc = forecast["initial_energy_wh"], forecast["initial_battery_soc_percent"]
        for hour, row in enumerate(rows):
            self.assertEqual(row["hour"], hour)
            self.assertEqual(row["battery_soc_start_percent"], soc)
            if hour:
                self.assertEqual(rows[hour - 1]["end"], row["start"])
            self.assertEqual(row["generated_energy_wh"], row["generation_w"])
            self.assertEqual(row["consumed_energy_wh"], row["consumption_w"])
            self.assertAlmostEqual(
                energy + row["generated_energy_wh"] - row["consumed_energy_wh"]
                + row["unserved_energy_wh"] - row["curtailed_energy_wh"], row["energy_wh"], places=3,
            )
            energy, soc = row["energy_wh"], row["battery_soc_percent"]
            self.assertTrue(0 <= soc <= 100)
            self.assertTrue(math.isfinite(row["temperature_c"]))
        self.assertEqual(rows[0]["start"], forecast["start"])
        self.assertEqual(rows[-1]["end"], forecast["end"])
        self.assertEqual(soc, power["final_soc_percent"])
        self.assertEqual(energy, power["final_energy_wh"])
        self.assertAlmostEqual(sum(r["generated_energy_wh"] for r in rows),
                               power["generated_energy_wh"], places=3)
        self.assertEqual(summary["sunlit_hours"] + summary["shadow_hours"], 24)
        self.assertEqual(summary["min_temperature_c"], min(r["temperature_c"] for r in rows))
        self.assertEqual(summary["max_temperature_c"], max(r["temperature_c"] for r in rows))
        self.assertEqual(summary["landing_zone_safe"], data["landing_zone"]["is_safe"])
        self.assertEqual(forecast["units"]["generation_w"], "W")
        self.assertEqual(forecast["units"]["energy_wh"], "Wh")

    def test_contiguous_shadow_and_blackout_summary(self):
        conditions = [MissionForecastTests.shadow] * 4 + [MissionForecastTests.light] * 20
        visible = [True] * 2 + [False] * 3 + [True] * 19
        with patch("server.mission.views.calculate_conditions", side_effect=conditions), patch(
            "server.mission.views.calculate_dte", side_effect=[
                {"visible": state, "earth_elevation_deg": 10 if state else -10} for state in visible
            ],
        ):
            result = calculate_mission(-85, 30, MODEL_EPOCH)
        self.assertEqual(result["summary"]["shadow_hours"], 4)
        self.assertEqual(result["summary"]["longest_shadow_h"], 4)
        self.assertEqual(result["summary"]["longest_dte_blackout_h"], 3)

    def test_repeated_requests_are_deterministic_and_independent(self):
        first = self.client.post("/api/mission/", MissionTests.payload, content_type="application/json")
        self.client.post("/api/mission/", {**MissionTests.payload, "latitude": -60},
                         content_type="application/json")
        second = self.client.post("/api/mission/", MissionTests.payload, content_type="application/json")
        self.assertEqual(first.json(), second.json())


class DustAndRadiationTests(SimpleTestCase):
    def test_dust_decreases_monotonically_and_is_bounded(self):
        previous = 100
        for hour in range(24):
            dust = calculate_dust(hour)
            self.assertAlmostEqual(dust["start_efficiency_percent"], previous)
            self.assertLess(dust["end_efficiency_percent"], dust["mean_efficiency_percent"])
            self.assertLess(dust["mean_efficiency_percent"], dust["start_efficiency_percent"])
            previous = dust["end_efficiency_percent"]
        aged = calculate_dust(1_000_000)
        self.assertEqual(aged["end_efficiency_percent"], 60)
        with self.assertRaises(ValueError):
            calculate_dust(-1)
        with self.assertRaises(ValueError):
            calculate_dust(0, duration_h=0)

    def test_zero_deposition_and_dust_power_loss(self):
        with patch("server.mission.views.DUST_DECAY_PER_HOUR", 0):
            self.assertEqual(calculate_dust(24)["mean_efficiency_percent"], 100)
        power = calculate_power(MissionForecastTests.light, 0, dust_efficiency=0.75)
        self.assertEqual(power["clean_generation_w"], 200)
        self.assertEqual(power["generation_w"], 150)
        self.assertEqual(power["dust_loss_w"], 50)
        dark = calculate_power(MissionForecastTests.shadow, 1_000, dust_efficiency=0.75)
        self.assertEqual(dark["generation_w"], 0)
        self.assertEqual(dark["dust_loss_w"], 0)

    def test_forecast_dust_affects_soc_and_energy_balance(self):
        # No saturation: isolate the effect of dust on stored energy.
        with patch("server.mission.views.INITIAL_SOC_PERCENT", 20), patch(
            "server.mission.views.calculate_conditions",
            return_value={**MissionForecastTests.light, "insolation_percent": 20},
        ):
            dusty = calculate_mission(-85, 30, MODEL_EPOCH)
            with patch("server.mission.views.DUST_DECAY_PER_HOUR", 0):
                clean = calculate_mission(-85, 30, MODEL_EPOCH)
        self.assertLess(dusty["power"]["final_soc_percent"], clean["power"]["final_soc_percent"])
        self.assertAlmostEqual(clean["power"]["final_energy_wh"] - dusty["power"]["final_energy_wh"],
                               dusty["dust"]["lost_generation_wh"], places=3)
        rows = dusty["forecast"]["timeline"]
        self.assertGreater(rows[0]["generation_w"], rows[-1]["generation_w"])
        self.assertEqual(rows[0]["dust"]["start_efficiency_percent"], 100)
        self.assertEqual(rows[-1]["dust"]["end_efficiency_percent"],
                         dusty["dust"]["final_efficiency_percent"])

    def test_radiation_exposure_and_shadow_background(self):
        overhead = {**MissionForecastTests.light, "sun_elevation_deg": 90}
        low_sun = {**overhead, "sun_elevation_deg": 5}
        light = calculate_radiation(overhead, MODEL_EPOCH)
        low = calculate_radiation(low_sun, MODEL_EPOCH)
        dark = calculate_radiation({**overhead, "is_shadowed": True}, MODEL_EPOCH)
        self.assertGreater(light["index"], low["index"])
        self.assertGreater(low["index"], dark["index"])
        self.assertGreaterEqual(dark["index"], 20)
        self.assertIsNone(light["flare_probability"])
        active = calculate_radiation(MissionForecastTests.shadow,
                                     MODEL_EPOCH + timedelta(days=6.75))
        self.assertEqual(active["risk_level"], "HIGH")
        self.assertGreater(active["index"], dark["index"])

    def test_radiation_hourly_summary_and_bounds(self):
        data = calculate_mission(-85, 30, MODEL_EPOCH)
        indices = [row["radiation"]["index"] for row in data["forecast"]["timeline"]]
        self.assertEqual(data["radiation"]["peak_index"], max(indices))
        self.assertAlmostEqual(data["radiation"]["mean_index"], sum(indices) / 24, places=3)
        self.assertFalse(data["radiation"]["observed_space_weather"])
        self.assertTrue(all(0 <= value <= 100 for value in indices))


class SafeHavenTests(SimpleTestCase):
    candidate = {
        "status": "SUCCESS", "slope_deg": 2,
        "landing_zone": {"safe_radius_estimate_m": 100},
        "power": {"minimum_soc_percent": 80, "final_soc_percent": 90},
        "radiation": {"peak_index": 30},
    }

    @patch("server.mission.views.calculate_mission")
    def test_success_does_not_trigger_scan(self, simulate):
        result = find_safe_haven(-85, 30, MODEL_EPOCH, {"status": "SUCCESS"})
        self.assertEqual(result["status"], "NOT_NEEDED")
        self.assertEqual(result["evaluated_candidates"], 0)
        self.assertIsNone(result["destination"])
        simulate.assert_not_called()

    def test_returns_nearest_success_and_preserves_timestamp(self):
        distances = []

        def simulate(lat, lon, timestamp):
            east, north = round((lat + 85) * 100_000), round(lon * 100_000)
            distances.append(math.hypot(east, north))
            return self.candidate if east ** 2 + north ** 2 >= 20_000 else {"status": "FAIL"}

        with patch("server.mission.views._offset_coordinates",
                   side_effect=lambda lat, lon, east, north: (-85 + east / 100_000, north / 100_000)), patch(
            "server.mission.views.calculate_mission", side_effect=simulate,
        ) as simulation:
            result = find_safe_haven(-85, 0, MODEL_EPOCH, {"status": "FAIL"})
        self.assertEqual(result["status"], "FOUND")
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(result["destination"]["distance_m"], 141.4214)
        self.assertFalse(result["route_validated"])
        self.assertTrue(all(call.args[2] == MODEL_EPOCH for call in simulation.call_args_list))

    @patch("server.mission.views.calculate_mission", return_value={"status": "FAIL"})
    def test_not_found_scan_is_bounded_and_nonrecursive(self, simulate):
        result = find_safe_haven(-85, 30, MODEL_EPOCH, {"status": "FAIL"})
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertIsNone(result["destination"])
        self.assertEqual(result["candidate_count"], 316)
        self.assertEqual(result["evaluated_candidates"], 316)
        self.assertEqual(simulate.call_count, 316)

    def test_invalid_neighbour_latitudes_are_not_simulated(self):
        with patch("server.mission.views.calculate_mission", return_value={"status": "FAIL"}) as simulate:
            result = find_safe_haven(-60, 0, MODEL_EPOCH, {"status": "FAIL"})
        self.assertLess(result["evaluated_candidates"], result["scanned_candidates"])
        self.assertTrue(all(-90 <= call.args[0] <= -60 for call in simulate.call_args_list))

    def test_api_finds_fully_validated_alternate_landing_site(self):
        latitude = -60.1
        centre_x = MOON_RADIUS_M * math.radians(latitude + 90)
        with patch("server.mission.views._elevation", return_value=0), patch(
            "server.mission.views._terrain_gradient",
            side_effect=lambda x, y, step=100: (1 if x < centre_x + 150 else 0, 0),
        ):
            response = self.client.post("/api/mission/", {
                "latitude": latitude, "longitude": 0, "timestamp": "2026-01-01T00:00:00Z",
            }, content_type="application/json")
            data = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(data["status"], "FAIL")
            self.assertEqual(data["safe_haven"]["status"], "FOUND")
            destination = data["safe_haven"]["destination"]
            self.assertLessEqual(destination["distance_m"], 1_000)
            alternative = self.client.post("/api/mission/", {
                "latitude": destination["latitude"], "longitude": destination["longitude"],
                "timestamp": destination["timestamp"],
            }, content_type="application/json").json()
        self.assertEqual(alternative["status"], "SUCCESS")
        self.assertTrue(alternative["landing_zone"]["is_safe"])
        self.assertEqual(alternative["safe_haven"]["status"], "NOT_NEEDED")

    def test_real_low_battery_cannot_be_accepted_as_haven(self):
        with patch("server.mission.views.calculate_conditions", return_value=MissionForecastTests.shadow):
            original = calculate_mission(-85, 30, MODEL_EPOCH)
            result = find_safe_haven(-85, 30, MODEL_EPOCH, original)
        self.assertEqual(result["status"], "NOT_FOUND")


class ThermalShockTests(SimpleTestCase):
    def test_reference_extremes_and_reverse_transition(self):
        heating = calculate_thermal_shock(-200, 120)
        cooling = calculate_thermal_shock(120, -200)
        self.assertEqual(heating["delta_temperature_c"], 320)
        self.assertEqual(heating["temperature_rate_c_per_h"], 320)
        self.assertAlmostEqual(heating["constrained_stress_mpa"], 515.2)
        self.assertEqual(heating["risk_level"], "HIGH")
        self.assertEqual(heating["risk_index"], 100)
        self.assertEqual(cooling["constrained_stress_mpa"], heating["constrained_stress_mpa"])
        self.assertEqual(cooling["delta_temperature_c"], -320)
        self.assertEqual(cooling["direction"], "COOLING")
        self.assertEqual(heating["direction"], "HEATING")

    def test_initial_and_constant_temperature_have_no_shock(self):
        for previous, expected_direction in ((None, "INITIAL"), (-200, "STABLE")):
            result = calculate_thermal_shock(previous, -200)
            self.assertEqual(result["constrained_stress_mpa"], 0)
            self.assertEqual(result["risk_index"], 0)
            self.assertEqual(result["direction"], expected_direction)
            self.assertEqual(result["has_previous_sample"], previous is not None)

    def test_rate_depends_on_interval_but_elastic_stress_depends_on_delta(self):
        fast = calculate_thermal_shock(-200, 120, interval_h=0.5)
        slow = calculate_thermal_shock(-200, 120, interval_h=2)
        self.assertEqual(fast["temperature_rate_c_per_h"], 640)
        self.assertEqual(slow["temperature_rate_c_per_h"], 160)
        self.assertEqual(fast["constrained_stress_mpa"], slow["constrained_stress_mpa"])

    def test_risk_thresholds(self):
        with patch("server.mission.views.THERMAL_YOUNG_MODULUS_GPA", 1), patch(
            "server.mission.views.THERMAL_EXPANSION_PER_K", 0.001,
        ), patch("server.mission.views.THERMAL_ALLOWABLE_STRESS_MPA", 100):
            for delta, expected in ((0, "LOW"), (49, "LOW"), (50, "MODERATE"),
                                    (99, "MODERATE"), (100, "HIGH")):
                self.assertEqual(calculate_thermal_shock(0, delta)["risk_level"], expected)

    def test_invalid_temperatures_or_interval_are_rejected(self):
        for previous, current, interval in ((0, float("nan"), 1), (0, float("inf"), 1),
                                            (-274, 0, 1), (0, None, 1), (0, 10, 0),
                                            (0, 10, -1), (0, 10, float("inf"))):
            with self.subTest(previous=previous, current=current, interval=interval):
                with self.assertRaises(ValueError):
                    calculate_thermal_shock(previous, current, interval)

    def test_hourly_thermal_transitions_and_summary(self):
        shadow = {**MissionForecastTests.shadow, "temperature_c": -200}
        sun = {**MissionForecastTests.light, "temperature_c": 120}
        with patch("server.mission.views.calculate_conditions",
                   side_effect=[shadow] * 2 + [sun] * 4 + [shadow] * 18):
            result = calculate_mission(-85, 30, MODEL_EPOCH)
        rows = result["forecast"]["timeline"]
        self.assertEqual(rows[0]["thermal_shock"]["direction"], "INITIAL")
        self.assertEqual(rows[2]["thermal_shock"]["illumination_transition"], "SHADOW_TO_SUN")
        self.assertEqual(rows[6]["thermal_shock"]["illumination_transition"], "SUN_TO_SHADOW")
        thermal = result["thermal_shock"]
        self.assertEqual(thermal["max_temperature_step_c"], 320)
        self.assertEqual(thermal["peak_stress_mpa"], 515.2)
        self.assertEqual(thermal["shadow_sun_transitions"], 2)
        self.assertEqual(thermal["high_risk_intervals"], 2)
        self.assertEqual(thermal["peak_risk_level"], "HIGH")
        self.assertEqual(result["summary"]["peak_thermal_stress_mpa"], 515.2)

    def test_reference_test_does_not_replace_actual_forecast(self):
        with patch("server.mission.views.calculate_conditions", return_value=MissionForecastTests.light):
            result = calculate_mission(-85, 30, MODEL_EPOCH)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["thermal_shock"]["peak_risk_level"], "LOW")
        self.assertEqual(result["thermal_shock"]["reference_stress_test"]["risk_level"], "HIGH")
        self.assertFalse(result["assumptions"]["thermal_shock_affects_verdict"])


class SignalLatencyTests(SimpleTestCase):
    def test_distance_extremes_and_light_speed_calculation(self):
        close = calculate_signal_latency(MODEL_EPOCH, dte_visible=True)
        far = calculate_signal_latency(MODEL_EPOCH + timedelta(days=14), dte_visible=True)
        self.assertEqual(close["distance_km"], 363_300)
        self.assertEqual(far["distance_km"], 405_500)
        self.assertLess(close["one_way_s"], far["one_way_s"])
        for result in (close, far):
            self.assertAlmostEqual(result["one_way_s"], result["distance_km"] / 299_792.458, places=7)
            self.assertAlmostEqual(result["round_trip_s"], 2 * result["one_way_s"], places=7)
            self.assertTrue(1.2 < result["one_way_s"] < 1.4)
            self.assertEqual(result["dte_one_way_s"], result["one_way_s"])
            self.assertEqual(result["dte_round_trip_s"], result["round_trip_s"])

    def test_no_dte_keeps_geometric_delay_but_direct_link_is_unavailable(self):
        result = calculate_signal_latency(MODEL_EPOCH, dte_visible=False)
        self.assertFalse(result["link_available"])
        self.assertGreater(result["one_way_s"], 0)
        self.assertIsNone(result["dte_one_way_s"])
        self.assertIsNone(result["dte_round_trip_s"])

    def test_periodicity_and_timestamps_before_epoch(self):
        first = calculate_signal_latency(MODEL_EPOCH - timedelta(days=7), dte_visible=True)
        repeated = calculate_signal_latency(MODEL_EPOCH + timedelta(days=21), dte_visible=True)
        self.assertEqual(first, repeated)
        self.assertEqual(first["distance_km"], 384_400)

    def test_hourly_latency_consistency_with_dte_and_summary(self):
        result = calculate_mission(-85, 30, MODEL_EPOCH)
        rows = result["forecast"]["timeline"]
        one_way = [row["signal_latency"]["one_way_s"] for row in rows]
        self.assertGreater(len(set(one_way)), 1)
        for row in rows:
            latency = row["signal_latency"]
            self.assertEqual(latency["link_available"], row["visible"])
            self.assertEqual(latency["dte_one_way_s"] is not None, row["visible"])
        self.assertEqual(result["signal_latency"]["initial"], rows[0]["signal_latency"])
        self.assertEqual(result["signal_latency"]["min_one_way_s"], min(one_way))
        self.assertEqual(result["signal_latency"]["max_one_way_s"], max(one_way))
        self.assertEqual(result["summary"]["max_signal_one_way_s"], max(one_way))
