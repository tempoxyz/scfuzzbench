import tempfile
import unittest
from pathlib import Path

from analysis import analyze
from analysis import events_to_cumulative


# Matrix/aggregated benchmark runs are flattened by the workflows collector
# (modules/tests.nu `scfuzzbench-collect-all-logs`) into a single per-target
# directory. Each round's log files are renamed to "<run_id>-<original_name>",
# where <run_id> is the safe-labeled path of that round's logs.zip and therefore
# always ends in "logs.zip". These tests pin the contract so multiple rounds are
# never collapsed into a single shared "unknown" run.
def matrix_filename(round_seg: str, target: str, name: str) -> str:
    return f"-{target}-foundry-master-{round_seg}-logs.zip-{name}"


FAILURE_LINE = (
    '{{"timestamp":{ts},"event":"failure",'
    '"target":"CryticToFoundry:invariant_a","type":"invariant"}}'
)


class MatrixRunIdentityTests(unittest.TestCase):
    def _write_matrix_logs(self, logs_dir: Path) -> None:
        # Two rounds for a target that finds a bug.
        aave = logs_dir / "foundry-master__target-aave-v4"
        aave.mkdir(parents=True)
        for round_seg in ("round-1", "round-2"):
            (aave / matrix_filename(round_seg, "aave-v4", "foundry.log")).write_text(
                FAILURE_LINE.format(ts=100) + "\n" + FAILURE_LINE.format(ts=200) + "\n",
                encoding="utf-8",
            )

        # Two rounds for a target with no bug events (the zero-bug case that
        # previously collapsed to a single seeded "unknown" run).
        liquity = logs_dir / "foundry-master__target-liquity-v2-governance"
        liquity.mkdir(parents=True)
        for round_seg in ("round-1", "round-2"):
            (liquity / matrix_filename(round_seg, "liquity-v2-governance", "foundry.log")).write_text(
                '{"timestamp":100,"event":"pulse","metrics":{"cumulative_edges_seen":1}}\n',
                encoding="utf-8",
            )

    def test_discover_recovers_per_round_run_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            self._write_matrix_logs(logs_dir)

            log_files = analyze.discover_log_files(logs_dir)
            run_ids = {lf.run_id for lf in log_files}
            # Each of the 4 round files must carry a distinct, non-null run id.
            self.assertEqual(len(run_ids), 4)
            self.assertNotIn(None, run_ids)
            for run_id in run_ids:
                self.assertTrue(run_id.endswith("logs.zip"))

    def test_parse_logs_keeps_rounds_distinct(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            self._write_matrix_logs(logs_dir)

            log_files = analyze.discover_log_files(logs_dir)
            events = analyze.parse_logs(logs_dir, None, log_files)

            aave_runs = {
                e.run_id for e in events if "aave-v4" in e.fuzzer_label
            }
            # The bug-finding target must show two distinct rounds, not one
            # collapsed "unknown" run.
            self.assertEqual(len(aave_runs), 2)
            self.assertNotIn("unknown", aave_runs)

    def test_inventory_seeds_one_entry_per_round(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            self._write_matrix_logs(logs_dir)

            runs = events_to_cumulative.inventory_runs_from_logs(
                logs_dir=logs_dir, run_id=None, raw_labels=True
            )
            liquity_keys = {
                run_key
                for fuzzer, run_key in runs
                if "liquity" in fuzzer
            }
            # Zero-bug target must still seed two distinct rounds.
            self.assertEqual(len(liquity_keys), 2)
            self.assertTrue(all(not k.startswith("unknown:") for k in liquity_keys))

    def test_cumulative_run_keys_align_between_events_and_inventory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            logs_dir = Path(tmp_dir)
            self._write_matrix_logs(logs_dir)

            log_files = analyze.discover_log_files(logs_dir)
            events = analyze.parse_logs(logs_dir, None, log_files)
            event_dicts = [
                {
                    "run_id": e.run_id,
                    "instance_id": e.instance_id,
                    "fuzzer": e.fuzzer_label,
                    "fuzzer_label": e.fuzzer_label,
                    "elapsed_seconds": e.elapsed_seconds,
                }
                for e in events
            ]

            rows = events_to_cumulative.build_cumulative_rows(
                event_dicts,
                include_zero=True,
                logs_dir=logs_dir,
                run_id=None,
                raw_labels=True,
            )
            # 4 rounds total across both targets => 4 distinct cumulative series.
            run_keys = {(fuzzer, run_key) for fuzzer, run_key, _, _ in rows}
            self.assertEqual(len(run_keys), 4)


if __name__ == "__main__":
    unittest.main()
