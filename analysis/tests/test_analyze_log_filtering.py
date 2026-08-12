import tempfile
import unittest
from pathlib import Path

from analysis import analyze
from analysis.events_to_cumulative import build_cumulative_rows


class AnalyzeLogFilteringTests(unittest.TestCase):
    def test_foundry_showmap_replay_is_not_parsed_as_benchmark_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            instance_dir = logs_dir / "i-abcd1234-foundry-git-test"
            instance_dir.mkdir(parents=True)
            (instance_dir / "foundry.log").write_text(
                "\n".join(
                    [
                        '{"timestamp":100,"event":"pulse","contract":"CryticToFoundry","metrics":{"cumulative_edges_seen":10,"corpus_count":5},"tps":10,"gps":100,"worker":{"id":0,"count":1}}',
                        '{"timestamp":105,"event":"failure","invariant":"benchmark_failure","target":"CryticToFoundry"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (instance_dir / "foundry_showmap.log").write_text(
                "\n".join(
                    [
                        '{"timestamp":1000,"event":"pulse","contract":"CryticToFoundry","metrics":{"cumulative_edges_seen":999,"corpus_count":999},"tps":999,"gps":9999,"worker":{"id":0,"count":1}}',
                        '{"timestamp":1001,"event":"failure","invariant":"benchmark_failure","target":"CryticToFoundry"}',
                        '{"timestamp":1002,"event":"failure","invariant":"replay_only_failure","target":"CryticToFoundry"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            log_files = analyze.discover_log_files(logs_dir)

            self.assertEqual([log_file.path.name for log_file in log_files], ["foundry.log"])
            events = analyze.parse_logs(logs_dir, "run-1", log_files)
            self.assertEqual([event.event for event in events], ["benchmark_failure"])
            self.assertEqual(events[0].elapsed_seconds, 5.0)
            self.assertEqual(Path(events[0].log_path).name, "foundry.log")
            cumulative = build_cumulative_rows(
                [event.__dict__ for event in events], include_zero=True
            )
            self.assertEqual(cumulative[-1][3], 1)

            throughput = analyze.parse_throughput_logs(logs_dir, "run-1", log_files)
            self.assertEqual([sample.tx_per_second for sample in throughput], [10.0])
            self.assertTrue(all(Path(sample.log_path).name == "foundry.log" for sample in throughput))

            progress = analyze.parse_progress_metrics_logs(logs_dir, "run-1", log_files)
            self.assertEqual([sample.coverage_proxy for sample in progress], [10.0])
            self.assertTrue(all(Path(sample.log_path).name == "foundry.log" for sample in progress))

    def test_parse_logs_ignores_runner_commands_log(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            instance_dir = logs_dir / "i-abcd1234-custom-fuzzer"
            instance_dir.mkdir(parents=True)
            (instance_dir / "runner_commands.log").write_text(
                "[2026-03-01 00:00:01] FAILURE should_not_be_parsed\n",
                encoding="utf-8",
            )

            log_files = analyze.discover_log_files(logs_dir)
            events = analyze.parse_logs(logs_dir, "run-1", log_files)
            self.assertEqual(events, [])

    def test_parse_throughput_logs_ignores_runner_commands_log(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            instance_dir = logs_dir / "i-abcd1234-custom-fuzzer"
            instance_dir.mkdir(parents=True)
            (instance_dir / "runner_commands.log").write_text(
                "[2026-03-01 00:00:01] tx/s: 123 gas/s: 456\n",
                encoding="utf-8",
            )

            log_files = analyze.discover_log_files(logs_dir)
            samples = analyze.parse_throughput_logs(logs_dir, "run-1", log_files)
            self.assertEqual(samples, [])

    def test_parse_progress_metrics_logs_ignores_runner_commands_log(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            instance_dir = logs_dir / "i-abcd1234-custom-fuzzer"
            instance_dir.mkdir(parents=True)
            (instance_dir / "runner_commands.log").write_text(
                "[2026-03-01 00:00:01] seq/s: 11 cov: 42 corpus: 7 failures: 1/2\n",
                encoding="utf-8",
            )

            log_files = analyze.discover_log_files(logs_dir)
            samples = analyze.parse_progress_metrics_logs(logs_dir, "run-1", log_files)
            self.assertEqual(samples, [])


if __name__ == "__main__":
    unittest.main()
