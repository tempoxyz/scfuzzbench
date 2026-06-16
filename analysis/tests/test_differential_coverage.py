import csv
import json
import tempfile
import unittest
from pathlib import Path

from analysis import analyze


class DifferentialCoverageTests(unittest.TestCase):
    def test_writes_normalized_showmap_campaigns_and_relscores(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master_showmap = (
                root
                / "logs"
                / "i-aaa-foundry-master"
                / "showmap"
                / "foundry-master__Suite__invariant_ok"
            )
            candidate_showmap = (
                root
                / "logs"
                / "i-bbb-foundry-candidate"
                / "showmap"
                / "foundry-candidate__Suite__invariant_ok"
            )
            master_showmap.mkdir(parents=True)
            candidate_showmap.mkdir(parents=True)
            (master_showmap / "trial-1.txt").write_text("1:1\n2:1\n3:0\n", encoding="utf-8")
            (candidate_showmap / "trial-1.txt").write_text("1:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            master_combined = (
                out_dir
                / "showmap_campaigns"
                / "combined"
                / "foundry-master"
                / "i-aaa-foundry-master__trial-1.txt"
            )
            candidate_by_test = (
                out_dir
                / "showmap_campaigns"
                / "by_test"
                / "Suite__invariant_ok"
                / "foundry-candidate"
                / "i-bbb-foundry-candidate__trial-1.txt"
            )
            self.assertEqual(master_combined.read_text(encoding="utf-8"), "1:1\n2:1\n")
            self.assertEqual(candidate_by_test.read_text(encoding="utf-8"), "1:1\n")

            with (out_dir / "differential_coverage_relscores.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            scores = {
                (row["campaign"], row["approach"]): row
                for row in rows
            }
            self.assertEqual(scores[("combined", "foundry-master")]["relscore"], "1.000000")
            self.assertEqual(scores[("combined", "foundry-candidate")]["relscore"], "0.000000")
            self.assertEqual(scores[("combined", "foundry-master")]["trials"], "1")
            self.assertEqual(scores[("combined", "foundry-master")]["covered_edges"], "2")
            self.assertEqual(
                scores[("by_test/Suite__invariant_ok", "foundry-master")]["relscore"],
                "1.000000",
            )
            with (out_dir / "differential_coverage_relcov.csv").open(newline="") as handle:
                relcov_rows = list(csv.DictReader(handle))
            relcovs = {
                (row["campaign"], row["approach"], row["reference_approach"]): row["relcov"]
                for row in relcov_rows
            }
            self.assertEqual(
                relcovs[("combined", "foundry-master", "foundry-candidate")],
                "1.000000",
            )
            self.assertEqual(
                relcovs[("combined", "foundry-candidate", "foundry-master")],
                "0.500000",
            )

            manifest = json.loads(
                (out_dir / "showmap_campaign_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["raw_trials"], 2)
            self.assertEqual(manifest["skipped"], [])
            self.assertIn("combined", manifest["campaigns"])

    def test_excludes_filtered_fuzzers_from_showmap_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master_showmap = root / "logs" / "i-aaa-foundry-master" / "showmap" / "foundry-master"
            candidate_showmap = (
                root / "logs" / "i-bbb-foundry-candidate" / "showmap" / "foundry-candidate"
            )
            master_showmap.mkdir(parents=True)
            candidate_showmap.mkdir(parents=True)
            (master_showmap / "trial-1.txt").write_text("1:1\n2:1\n", encoding="utf-8")
            (candidate_showmap / "trial-1.txt").write_text("1:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(
                root / "logs", out_dir, {"foundry-candidate"}
            )

            with (out_dir / "differential_coverage_relscores.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["campaign"], "combined")
            self.assertEqual(rows[0]["approach"], "foundry-master")
            self.assertEqual(rows[0]["relscore"], "0.000000")
            with (out_dir / "differential_coverage_relcov.csv").open(newline="") as handle:
                relcov_rows = list(csv.DictReader(handle))
            self.assertEqual(len(relcov_rows), 1)
            self.assertEqual(relcov_rows[0]["approach"], "foundry-master")
            self.assertEqual(relcov_rows[0]["reference_approach"], "foundry-master")
            self.assertEqual(relcov_rows[0]["relcov"], "1.000000")
            self.assertTrue(
                (out_dir / "showmap_campaigns" / "combined" / "foundry-master").is_dir()
            )
            self.assertFalse(
                (out_dir / "showmap_campaigns" / "combined" / "foundry-candidate").exists()
            )

    def test_clears_stale_showmap_campaigns_on_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master_showmap = root / "logs" / "i-aaa-foundry-master" / "showmap" / "foundry-master"
            candidate_showmap = (
                root / "logs" / "i-bbb-foundry-candidate" / "showmap" / "foundry-candidate"
            )
            master_showmap.mkdir(parents=True)
            candidate_showmap.mkdir(parents=True)
            (master_showmap / "trial-1.txt").write_text("1:1\n2:1\n", encoding="utf-8")
            (candidate_showmap / "trial-1.txt").write_text("1:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)
            self.assertTrue(
                (out_dir / "showmap_campaigns" / "combined" / "foundry-candidate").exists()
            )

            analyze.write_differential_coverage_outputs(
                root / "logs", out_dir, {"foundry-candidate"}
            )
            self.assertTrue(
                (out_dir / "showmap_campaigns" / "combined" / "foundry-master").exists()
            )
            self.assertFalse(
                (out_dir / "showmap_campaigns" / "combined" / "foundry-candidate").exists()
            )
            manifest = json.loads(
                (out_dir / "showmap_campaign_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                sorted(manifest["campaigns"]["combined"].keys()),
                ["foundry-master"],
            )

    def test_parses_invariant_showmap_dirs_as_suite_campaigns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master_showmap = (
                root
                / "logs"
                / "i-aaa-foundry-master"
                / "showmap"
                / "foundry-master__test_ShowmapCounter.t.sol_ShowmapCounterTest"
            )
            candidate_showmap = (
                root
                / "logs"
                / "i-bbb-foundry-candidate"
                / "showmap"
                / "foundry-candidate__test_ShowmapCounter.t.sol_ShowmapCounterTest"
            )
            master_showmap.mkdir(parents=True)
            candidate_showmap.mkdir(parents=True)
            (master_showmap / "trial-1.txt").write_text("1:1\n2:1\n", encoding="utf-8")
            (candidate_showmap / "trial-1.txt").write_text("1:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            suite_name = "test_ShowmapCounter.t.sol_ShowmapCounterTest"
            self.assertTrue(
                (
                    out_dir
                    / "showmap_campaigns"
                    / "by_test"
                    / suite_name
                    / "foundry-master"
                    / "i-aaa-foundry-master__trial-1.txt"
                ).is_file()
            )
            self.assertFalse(
                (
                    out_dir
                    / "showmap_campaigns"
                    / "combined"
                    / "foundry-master__test_ShowmapCounter.t.sol_ShowmapCounterTest"
                ).exists()
            )

            with (out_dir / "differential_coverage_relscores.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            scores = {(row["campaign"], row["approach"]): row["relscore"] for row in rows}
            self.assertEqual(scores[("combined", "foundry-master")], "1.000000")
            self.assertEqual(scores[(f"by_test/{suite_name}", "foundry-candidate")], "0.000000")

    def test_parses_real_foundry_showmap_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap_root = root / "logs" / "i-live-foundry-live" / "showmap"
            invariant_dir = (
                showmap_root
                / "foundry-live__test_CryticToFoundry.t.sol_CryticToFoundry"
            )
            fuzz_dir = (
                showmap_root
                / "foundry-live__test_CryticToFoundry.t.sol_CryticToFoundry__testFuzz_SetNumber"
            )
            invariant_dir.mkdir(parents=True)
            fuzz_dir.mkdir(parents=True)
            (invariant_dir / "trial-live.txt").write_text("a:1\n", encoding="utf-8")
            (fuzz_dir / "trial-live.txt").write_text("b:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            invariant_campaign = (
                out_dir
                / "showmap_campaigns"
                / "by_test"
                / "test_CryticToFoundry.t.sol_CryticToFoundry"
                / "foundry-live"
                / "i-live-foundry-live__trial-live.txt"
            )
            fuzz_campaign = (
                out_dir
                / "showmap_campaigns"
                / "by_test"
                / "test_CryticToFoundry.t.sol_CryticToFoundry__testFuzz_SetNumber"
                / "foundry-live"
                / "i-live-foundry-live__trial-live.txt"
            )
            self.assertEqual(invariant_campaign.read_text(encoding="utf-8"), "a:1\n")
            self.assertEqual(fuzz_campaign.read_text(encoding="utf-8"), "b:1\n")

    def test_combined_campaign_merges_multiple_raw_foundry_dirs_per_approach(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap_root = root / "logs" / "i-live" / "showmap"
            raw_dirs = {
                "foundry-master__Suite": "a:1\nb:1\n",
                "foundry-master__Suite__testFuzz_x": "c:1\n",
                "foundry-candidate__Suite": "a:1\n",
                "foundry-candidate__Suite__testFuzz_x": "d:1\n",
            }
            for dirname, body in raw_dirs.items():
                path = showmap_root / dirname
                path.mkdir(parents=True)
                (path / "trial-1.txt").write_text(body, encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            combined = out_dir / "showmap_campaigns" / "combined"
            self.assertEqual(
                sorted(path.name for path in combined.iterdir() if path.is_dir()),
                ["foundry-candidate", "foundry-master"],
            )
            self.assertEqual(
                (combined / "foundry-master" / "i-live__trial-1.txt").read_text(
                    encoding="utf-8"
                ),
                "a:1\nb:1\nc:1\n",
            )
            self.assertEqual(
                (combined / "foundry-candidate" / "i-live__trial-1.txt").read_text(
                    encoding="utf-8"
                ),
                "a:1\nd:1\n",
            )

            manifest = json.loads(
                (out_dir / "showmap_campaign_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["raw_trials"], 4)
            self.assertEqual(
                sorted(manifest["campaigns"]["combined"].keys()),
                ["foundry-candidate", "foundry-master"],
            )

            with (out_dir / "differential_coverage_relscores.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            scores = {
                (row["campaign"], row["approach"]): row["relscore"]
                for row in rows
            }
            self.assertEqual(scores[("combined", "foundry-master")], "2.000000")
            self.assertEqual(scores[("combined", "foundry-candidate")], "1.000000")
            with (out_dir / "differential_coverage_relcov.csv").open(newline="") as handle:
                relcov_rows = list(csv.DictReader(handle))
            relcovs = {
                (row["campaign"], row["approach"], row["reference_approach"]): row["relcov"]
                for row in relcov_rows
            }
            self.assertEqual(
                relcovs[("combined", "foundry-master", "foundry-candidate")],
                "0.500000",
            )
            self.assertEqual(
                relcovs[("combined", "foundry-candidate", "foundry-master")],
                "0.333333",
            )

    def test_combined_is_not_a_suite_name_sentinel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap_dir = root / "logs" / "i-live" / "showmap" / "foundry-master__combined"
            showmap_dir.mkdir(parents=True)
            (showmap_dir / "trial-1.txt").write_text("a:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            self.assertTrue(
                (
                    out_dir
                    / "showmap_campaigns"
                    / "by_test"
                    / "combined"
                    / "foundry-master"
                    / "i-live__trial-1.txt"
                ).is_file()
            )

    def test_sanitizes_special_path_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap_root = root / "logs" / "i-live" / "showmap"
            unsafe_dir = showmap_root / "..__Suite"
            safe_dir = showmap_root / "candidate__Suite"
            unsafe_dir.mkdir(parents=True)
            safe_dir.mkdir(parents=True)
            (unsafe_dir / "trial-1.txt").write_text("a:1\n", encoding="utf-8")
            (safe_dir / "trial-1.txt").write_text("b:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            combined = out_dir / "showmap_campaigns" / "combined"
            self.assertTrue((combined / "unknown").is_dir())
            self.assertTrue((combined / "candidate").is_dir())
            self.assertFalse((out_dir / "showmap_campaigns" / "i-live__trial-1.txt").exists())


if __name__ == "__main__":
    unittest.main()
