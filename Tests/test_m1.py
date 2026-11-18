import datetime as dt
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from Clock import clock
from Config import config
import Entry as main


def valid_config():
    return {
        "napcat": {"api": "http://localhost:3000", "token": "token"},
        "target": {"group": "test"},
        "admin": 123456789,
        "llm": {"api_key": "key", "base_url": "https://example.com/v1", "model": "test-model"},
        "feishu": {"config_path": "feishu.json"},
    }


class ConfigTests(unittest.TestCase):
    def test_load_merges_nested_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(valid_config()), encoding="utf-8")
            loaded = config.load(path)

        self.assertEqual(loaded["times"], ["09:00", "18:00"])
        self.assertEqual(loaded["llm"]["temperature"], 0.7)
        self.assertEqual(loaded["risk"]["near_days"], 5)

    def test_ntp_servers_default_and_configured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(valid_config()), encoding="utf-8")
            self.assertEqual(config.load(path)["ntp_servers"], ["ntp.aliyun.com", "ntp.tencent.com"])

            values = valid_config()
            values["ntp_servers"] = ["time.example.com"]
            path.write_text(json.dumps(values), encoding="utf-8")
            self.assertEqual(config.load(path)["ntp_servers"], ["time.example.com"])

    def test_defaults_are_not_shared_between_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(valid_config()), encoding="utf-8")

            first = config.load(path)
            first["risk"]["aliases"]["Alice"] = 123
            second = config.load(path)

        self.assertEqual(second["risk"]["aliases"], {})

    def test_missing_required_value_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "napcat.token"):
                config.load(path)

    def test_required_value_is_not_satisfied_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            values = valid_config()
            del values["napcat"]["api"]
            path.write_text(json.dumps(values), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "napcat.api"):
                config.load(path)

    def test_invalid_schedule_fails(self):
        for times in ([], "09:00", ["24:00"], ["9:00"], ["12:60:00"]):
            with self.subTest(times=times), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"
                values = valid_config()
                values["times"] = times
                path.write_text(json.dumps(values), encoding="utf-8")

                with self.assertRaises(ValueError):
                    config.load(path)

    def test_full_width_colon_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            values = valid_config()
            values["times"] = ["０９：００"]
            path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(ValueError):
                config.load(path)

            values["times"] = ["09：00"]
            path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(config.load(path)["times"], ["09:00"])

    def test_missing_file_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "无法读取配置"):
                config.load(Path(directory) / "missing.json")


class ClockTests(unittest.TestCase):
    @staticmethod
    def ntp_packet(epoch):
        packet = bytearray(48)
        packet[0] = 0x24
        packet[1] = 2
        struct.pack_into("!II", packet, 40, epoch + clock.NTP_EPOCH_OFFSET, 0)
        return bytes(packet)

    class FakeSocket:
        def __init__(self, response=None, error=None):
            self.response = response
            self.error = error

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def settimeout(self, timeout):
            self.timeout = timeout

        def sendto(self, request, address):
            self.request = request
            self.address = address
            if self.error:
                raise self.error

        def recvfrom(self, _size):
            return self.response, ("127.0.0.1", 123)

    def test_sync_uses_ntp_and_now_advances_in_utc8(self):
        expected_epoch = int(dt.datetime(2026, 11, 17, 4, 0, tzinfo=dt.timezone.utc).timestamp())
        fake_socket = self.FakeSocket(self.ntp_packet(expected_epoch))
        clk = clock.Clock(("ntp.test",))

        with patch("Clock.clock.socket.socket", return_value=fake_socket), patch(
            "Clock.clock.time.monotonic", side_effect=(100.0, 101.0, 101.0)
        ):
            self.assertEqual(clk.sync(), "ntp://ntp.test")
            now = clk.now()
            today = clk.today()

        self.assertEqual(fake_socket.address, ("ntp.test", 123))
        self.assertEqual(fake_socket.request, b"\x1b" + bytes(47))
        self.assertEqual(now, dt.datetime(2026, 11, 17, 12, 0, 1, tzinfo=clock.UTC8))
        self.assertEqual(today, dt.date(2026, 11, 17))

    def test_sync_tries_next_server_after_failure(self):
        expected_epoch = int(dt.datetime(2026, 11, 17, 4, 0, tzinfo=dt.timezone.utc).timestamp())
        sockets = [
            self.FakeSocket(error=OSError("unreachable")),
            self.FakeSocket(self.ntp_packet(expected_epoch)),
        ]
        clk = clock.Clock(("first.test", "second.test"))

        with patch("Clock.clock.socket.socket", side_effect=sockets), patch("Clock.clock.time.monotonic", return_value=1.0):
            self.assertEqual(clk.sync(), "ntp://second.test")

    def test_sync_fails_without_system_clock_fallback(self):
        clk = clock.Clock(("ntp.test",))
        with patch("Clock.clock.socket.socket", side_effect=OSError("unreachable")):
            with self.assertRaisesRegex(RuntimeError, "NTP 校时失败"):
                clk.sync()

    def test_invalid_ntp_packet_fails(self):
        packet = bytearray(self.ntp_packet(1))
        packet[1] = 0
        clk = clock.Clock(("ntp.test",))
        with patch("Clock.clock.socket.socket", return_value=self.FakeSocket(bytes(packet))):
            with self.assertRaisesRegex(RuntimeError, "无效的 NTP 响应"):
                clk.sync()

    def test_now_requires_successful_sync(self):
        with self.assertRaisesRegex(RuntimeError, "尚未成功"):
            clock.Clock(("ntp.test",)).now()


class SchedulerTests(unittest.TestCase):
    def test_due_slot_matches_inside_and_on_tolerance(self):
        state = {"fired": {}, "last_run_at": ""}
        now = dt.datetime(2026, 11, 17, 9, 0, 30, tzinfo=clock.UTC8)
        self.assertEqual(main.due_slot(["09:00"], now, state), "09:00")

    def test_due_slot_misses_outside_tolerance(self):
        state = {"fired": {}, "last_run_at": ""}
        now = dt.datetime(2026, 11, 17, 9, 0, 31, tzinfo=clock.UTC8)
        self.assertIsNone(main.due_slot(["09:00"], now, state))

    def test_due_slot_includes_microseconds_in_tolerance(self):
        state = {"fired": {}, "last_run_at": ""}
        now = dt.datetime(2026, 11, 17, 9, 0, 30, 900000, tzinfo=clock.UTC8)
        self.assertIsNone(main.due_slot(["09:00"], now, state))

    def test_due_slot_uses_ring_distance_across_midnight(self):
        state = {"fired": {}, "last_run_at": ""}
        now = dt.datetime(2026, 11, 18, 0, 0, 20, tzinfo=clock.UTC8)
        self.assertEqual(main.due_slot(["23:59:50"], now, state), "23:59:50")

    def test_due_slot_skips_fired_slot_for_today(self):
        state = {"fired": {"2026-11-17": ["09:00"]}, "last_run_at": ""}
        now = dt.datetime(2026, 11, 17, 9, 0, tzinfo=clock.UTC8)
        self.assertIsNone(main.due_slot(["09:00"], now, state))

    def test_midnight_window_checks_slot_occurrence_date(self):
        state = {"fired": {"2026-11-17": ["23:59:50"]}, "last_run_at": ""}
        now = dt.datetime(2026, 11, 18, 0, 0, 20, tzinfo=clock.UTC8)
        self.assertIsNone(main.due_slot(["23:59:50"], now, state))

    def test_read_corrupt_state_warns_and_returns_empty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("not json", encoding="utf-8")

            with self.assertLogs(main.LOG, level="WARNING"):
                state = main.read_state(path)

        self.assertEqual(state, {"fired": {}, "last_run_at": ""})

    def test_read_invalid_state_shape_returns_empty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"fired": []}), encoding="utf-8")

            with self.assertLogs(main.LOG, level="WARNING"):
                state = main.read_state(path)

        self.assertEqual(state, {"fired": {}, "last_run_at": ""})

    def test_write_state_round_trips_and_replaces_atomically(self):
        state = {"fired": {"2026-11-17": ["09:00"]}, "last_run_at": "2026-11-17T09:00:00+08:00"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            main.write_state(path, state)

            self.assertEqual(main.read_state(path), state)
            self.assertFalse(path.with_name("state.json.tmp").exists())

    def test_service_runs_once_on_start_and_marks_matching_slot(self):
        now = dt.datetime(2026, 11, 17, 9, 0, 10, tzinfo=clock.UTC8)
        clk = Mock()
        clk.now.return_value = now
        state = {"fired": {}, "last_run_at": ""}
        cfg = {"state_path": "state.json", "times": ["09:00"], "ntp_servers": ["ntp.test"]}

        with patch("Entry.clock_mod.Clock", return_value=clk) as clock_cls, patch(
            "Entry.read_state", return_value=state
        ), patch("Entry.write_state") as write_state, patch(
            "Entry.run_and_report", return_value=True
        ) as run, patch("Entry.time.sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                main.service(cfg)

        clock_cls.assert_called_once_with(("ntp.test",))
        clk.sync.assert_called_once_with()
        run.assert_called_once_with(cfg, clk)
        write_state.assert_called_once_with("state.json", state)
        self.assertEqual(state["fired"], {"2026-11-17": ["09:00"]})
        self.assertEqual(state["last_run_at"], now.isoformat())


class FeishuTests(unittest.TestCase):
    def test_fetch_requires_export_config(self):
        """缺少导出配置文件时抛 RuntimeError。"""
        cfg = {"feishu": {"config_path": "/nonexistent/config.json"}}
        from Feishu import feishu
        with self.assertRaisesRegex(RuntimeError, "fetch:"):
            feishu.fetch(cfg)


if __name__ == "__main__":
    unittest.main()
