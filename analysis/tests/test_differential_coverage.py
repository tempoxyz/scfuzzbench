import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from analysis import analyze

try:
    # Optional: only used to cross-check the local implementation against the reference.
    # analyze.py no longer depends on this package at runtime.
    from differential_coverage import DifferentialCoverage
except ImportError:
    DifferentialCoverage = None


@unittest.skipUnless(
    DifferentialCoverage is not None, "differential_coverage not installed"
)
class RelscoreParityTests(unittest.TestCase):
    """The local linear calculate_relscores/relcovs must match the upstream library."""

    @staticmethod
    def _random_campaign(rng):
        edge_universe = [f"e{i}" for i in range(rng.randint(1, 40))]
        campaign = {}
        for a in range(rng.randint(1, 5)):
            trials = {}
            for t in range(rng.randint(1, 6)):
                k = rng.randint(1, len(edge_universe))
                trials[f"t{t}"] = set(rng.sample(edge_universe, k))  # always non-empty
            campaign[f"approach{a}"] = trials
        return campaign

    def _assert_relscore_parity(self, campaign):
        assert DifferentialCoverage is not None  # guaranteed by skipUnless
        expected = dict(DifferentialCoverage(campaign).relscores())
        actual = analyze.calculate_relscores(campaign)
        self.assertEqual(set(expected), set(actual))
        for approach in expected:
            self.assertAlmostEqual(expected[approach], actual[approach], places=9)

    def _assert_relcov_parity(self, campaign):
        assert DifferentialCoverage is not None  # guaranteed by skipUnless
        dc = DifferentialCoverage(campaign)
        expected = {
            a: {r: dc.approaches[a].relcov(dc.approaches[r]) for r in dc.approaches}
            for a in dc.approaches
        }
        actual = analyze.calculate_relcovs(campaign)
        self.assertEqual(set(expected), set(actual))
        for a in expected:
            self.assertEqual(set(expected[a]), set(actual[a]))
            for r in expected[a]:
                self.assertAlmostEqual(expected[a][r], actual[a][r], places=9)

    def test_matches_library_on_random_campaigns(self):
        rng = random.Random(1234)
        for _ in range(500):
            campaign = self._random_campaign(rng)
            self._assert_relscore_parity(campaign)
            self._assert_relcov_parity(campaign)

    def test_matches_library_on_hand_picked_cases(self):
        cases = [
            # single approach -> every relscore is 0
            {"only": {"t1": {"a", "b"}}},
            # disjoint coverage
            {"x": {"t1": {"a"}}, "y": {"t1": {"b"}}},
            # multiple trials with partial overlap
            {
                "x": {"t1": {"a", "b"}, "t2": {"b", "c"}},
                "y": {"t1": {"a"}, "t2": {"a", "c"}, "t3": {"d"}},
            },
        ]
        for campaign in cases:
            self._assert_relscore_parity(campaign)
            self._assert_relcov_parity(campaign)


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
            self.assertNotIn(("combined", "foundry-master", "foundry-master"), relcovs)
            self.assertEqual(
                relcovs[("combined", "foundry-master", "foundry-candidate")],
                "1.000000",
            )
            self.assertEqual(
                relcovs[("combined", "foundry-candidate", "foundry-master")],
                "0.500000",
            )
            with (out_dir / "differential_coverage_summary.csv").open(newline="") as handle:
                summary_rows = list(csv.DictReader(handle))
            summary = {(row["campaign"], row["candidate"]): row for row in summary_rows}
            self.assertEqual(
                summary[("combined", "foundry-candidate")]["verdict"],
                "regression",
            )
            self.assertEqual(
                summary[("combined", "foundry-candidate")]["candidate_covers_baseline"],
                "0.500000",
            )

            manifest = json.loads(
                (out_dir / "showmap_campaign_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["raw_trials"], 2)
            self.assertEqual(manifest["skipped"], [])
            self.assertIn("combined", manifest["campaigns"])
            self.assertIn("work_items", manifest["campaigns"]["combined"])

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
            self.assertEqual(relcov_rows, [])
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
                sorted(manifest["campaigns"]["combined"]["approaches"].keys()),
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
                sorted(manifest["campaigns"]["combined"]["approaches"].keys()),
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

    def test_writes_human_summary_for_master_pr_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap_root = root / "logs"
            master_showmap = showmap_root / "i-aaa-master" / "showmap" / "master__Suite"
            pr_showmap = showmap_root / "i-bbb-pr-15206" / "showmap" / "pr-15206__Suite"
            master_showmap.mkdir(parents=True)
            pr_showmap.mkdir(parents=True)
            (master_showmap / "trial-1.txt").write_text(
                "a:1\nb:1\nc:1\nd:1\n", encoding="utf-8"
            )
            (pr_showmap / "trial-1.txt").write_text(
                "a:1\nb:1\nc:1\ne:1\n", encoding="utf-8"
            )

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(root / "logs", out_dir)

            with (out_dir / "differential_coverage_relcov.csv").open(newline="") as handle:
                relcov_rows = list(csv.DictReader(handle))
            self.assertEqual(len(relcov_rows), 4)
            self.assertFalse(
                any(row["approach"] == row["reference_approach"] for row in relcov_rows)
            )

            with (out_dir / "differential_coverage_summary.csv").open(newline="") as handle:
                summary_rows = list(csv.DictReader(handle))

            combined = next(row for row in summary_rows if row["campaign"] == "combined")
            self.assertEqual(combined["baseline"], "master")
            self.assertEqual(combined["candidate"], "pr-15206")
            self.assertEqual(combined["verdict"], "regression")
            self.assertEqual(combined["candidate_covers_baseline"], "0.750000")
            self.assertEqual(combined["baseline_covers_candidate"], "0.750000")

    def test_target_labels_create_target_campaign_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            for target, master_edges, pr_edges in [
                ("aave", "a:1\nb:1\n", "a:1\nc:1\n"),
                ("nerite", "x:1\ny:1\n", "x:1\ny:1\nz:1\n"),
            ]:
                master = logs / f"i-master__target-{target}" / "showmap" / "master__Suite"
                pr = logs / f"i-pr__target-{target}" / "showmap" / "pr-1__Suite"
                master.mkdir(parents=True)
                pr.mkdir(parents=True)
                (master / "trial-1.txt").write_text(master_edges, encoding="utf-8")
                (pr / "trial-1.txt").write_text(pr_edges, encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(logs, out_dir)

            with (out_dir / "differential_coverage_summary.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            campaigns = {row["campaign"] for row in rows}

            self.assertIn("by_target/aave", campaigns)
            self.assertIn("by_target/nerite", campaigns)
            self.assertIn("combined", campaigns)

    def test_seed_labels_pair_by_seed_and_collapse_campaign_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            for label, approach, edges_by_suite in [
                ("foundry-master", "foundry-master", {"SuiteA": "a:1\n", "SuiteB": "b:1\n"}),
                ("foundry-candidate", "foundry-candidate", {"SuiteA": "a:1\n", "SuiteB": "c:1\n"}),
            ]:
                for suite, edges in edges_by_suite.items():
                    showmap = (
                        logs
                        / f"{label}__target-aave__seed-101"
                        / "showmap"
                        / f"{approach}__{suite}"
                    )
                    showmap.mkdir(parents=True)
                    (showmap / "trial-1.txt").write_text(edges, encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(logs, out_dir)

            with (out_dir / "differential_coverage_summary.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            target_row = next(row for row in rows if row["campaign"] == "by_target/aave")
            self.assertEqual(target_row["n_trials"], "1")
            self.assertEqual(target_row["paired"], "true")
            self.assertEqual(target_row["pairing_rate"], "1.000000")
            self.assertEqual(target_row["test_name"], "paired-sign")

            campaign_file = (
                out_dir
                / "showmap_campaigns"
                / "by_target"
                / "aave"
                / "foundry-master"
                / "seed-101.txt"
            )
            self.assertEqual(campaign_file.read_text(encoding="utf-8"), "a:1\nb:1\n")

    def test_seed_labels_do_not_fall_back_to_unpaired_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs = root / "logs"
            master = logs / "foundry-master__target-aave__seed-1" / "showmap" / "foundry-master__Suite"
            candidate = (
                logs
                / "foundry-candidate__target-aave__seed-2"
                / "showmap"
                / "foundry-candidate__Suite"
            )
            master.mkdir(parents=True)
            candidate.mkdir(parents=True)
            (master / "trial-1.txt").write_text("a:1\n", encoding="utf-8")
            (candidate / "trial-1.txt").write_text("a:1\nb:1\n", encoding="utf-8")

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(logs, out_dir)

            with (out_dir / "differential_coverage_summary.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            target_row = next(row for row in rows if row["campaign"] == "by_target/aave")
            self.assertEqual(target_row["n_trials"], "0")
            self.assertEqual(target_row["paired"], "false")
            self.assertEqual(target_row["test_name"], "paired-seed-required")
            self.assertEqual(target_row["decision"], "inconclusive")

            state = json.loads(
                (out_dir / "differential_coverage_sequential_state.json").read_text(
                    encoding="utf-8"
                )
            )
            target_state = next(
                row for row in state["rows"] if row["campaign"] == "by_target/aave"
            )
            self.assertIn("unpaired fallback disabled", target_state["reason"])

    def test_differential_coverage_verdict_thresholds(self):
        self.assertEqual(
            analyze.differential_coverage_verdict(0.99, 10.0, 10.0),
            "improvement",
        )
        self.assertEqual(
            analyze.differential_coverage_verdict(0.96, 11.0, 10.0),
            "needs-review",
        )
        self.assertEqual(
            analyze.differential_coverage_verdict(0.94, 20.0, 10.0),
            "regression",
        )
        self.assertEqual(
            analyze.differential_coverage_verdict(0.99, 9.7, 10.0),
            "regression",
        )

    def test_sequential_state_does_not_emit_scheduler_elimination(self):
        campaign = {
            "master": {f"s{i}": {"a", "b", "c", "d"} for i in range(3)},
            "pr-1": {f"s{i}": {"a"} for i in range(3)},
        }
        relscores = analyze.calculate_relscores(campaign)
        relcovs = analyze.calculate_relcovs(campaign)
        summary = analyze.build_differential_coverage_summary_rows(
            "by_target/aave", relscores, relcovs
        )
        rows, directive = analyze.build_sequential_state_rows(
            summary, {"by_target/aave": campaign}, max_trials_per_arm=12
        )
        self.assertEqual(rows[0]["decision"], "inconclusive")
        self.assertEqual(rows[0]["trials_saved_vs_fixed_n"], 0)
        self.assertEqual(directive["aggregate"]["eliminated_count"], 0)
        self.assertEqual(directive["schedule"][0]["decision"], "inconclusive")

    def test_sequential_state_does_not_auto_declare_winner_without_valid_inference(self):
        campaign = {
            "master": {f"s{i}": {"a", "b", "c"} for i in range(4)},
            "pr-1": {f"s{i}": {"a", "b", "c", f"x{i}", f"y{i}"} for i in range(4)},
        }
        relscores = analyze.calculate_relscores(campaign)
        relcovs = analyze.calculate_relcovs(campaign)
        summary = analyze.build_differential_coverage_summary_rows(
            "by_target/nerite", relscores, relcovs
        )
        rows, directive = analyze.build_sequential_state_rows(
            summary, {"by_target/nerite": campaign}, max_trials_per_arm=12
        )
        self.assertNotEqual(rows[0]["decision"], "winner")
        self.assertFalse(directive["aggregate"]["automated_winner_enabled"])

    def test_sequential_state_noisy_equal_means_never_auto_wins_across_peeks(self):
        false_winners = 0
        for run in range(50):
            full_campaign = {
                "master": {
                    f"s{i}": {"shared", f"m{(i + run) % 3}", f"n{i % 2}"}
                    for i in range(6)
                },
                "pr-1": {
                    f"s{i}": {"shared", f"p{(i + run) % 3}", f"n{i % 2}"}
                    for i in range(6)
                },
            }
            for wave_end in range(2, 7):
                campaign = {
                    arm: {
                        trial_id: edges
                        for trial_id, edges in trials.items()
                        if int(trial_id[1:]) < wave_end
                    }
                    for arm, trials in full_campaign.items()
                }
                relscores = analyze.calculate_relscores(campaign)
                relcovs = analyze.calculate_relcovs(campaign)
                summary = analyze.build_differential_coverage_summary_rows(
                    "by_target/null", relscores, relcovs
                )
                rows, _ = analyze.build_sequential_state_rows(
                    summary, {"by_target/null": campaign}, max_trials_per_arm=6
                )
                false_winners += int(rows[0]["decision"] == "winner")
        self.assertLessEqual(false_winners / 50, 0.05)

    def test_sequential_state_records_missing_count_and_does_not_block(self):
        campaign = {
            "master": {"s1": {"a", "b"}, "s2": {"a", "b"}},
            "pr-1": {"s1": {"a", "b"}, "s2": {"a", "b", "c"}},
        }
        relscores = analyze.calculate_relscores(campaign)
        relcovs = analyze.calculate_relcovs(campaign)
        summary = analyze.build_differential_coverage_summary_rows(
            "by_target/slow", relscores, relcovs
        )
        rows, _ = analyze.build_sequential_state_rows(summary, {"by_target/slow": campaign})
        self.assertEqual(rows[0]["decision"], "inconclusive")
        self.assertEqual(rows[0]["missing_count"], 0)

    def test_sequential_state_models_confirmation_cache_reuse(self):
        campaign = {
            "master": {"s1": {"a", "b"}, "s2": {"a", "b"}},
            "pr-1": {"s1": {"a", "b", "c"}, "s2": {"a", "b", "d"}},
        }
        relscores = analyze.calculate_relscores(campaign)
        relcovs = analyze.calculate_relcovs(campaign)
        summary = analyze.build_differential_coverage_summary_rows(
            "by_target/aave", relscores, relcovs
        )
        rows, directive = analyze.build_sequential_state_rows(
            summary, {"by_target/aave": campaign}, max_trials_per_arm=3
        )
        self.assertEqual(rows[0]["trials_spent"], 2)
        if rows[0]["decision"] == "continue":
            self.assertEqual(directive["schedule"][0]["next_seeds"], [])

    def test_sequential_state_exercises_paired_and_unpaired_paths(self):
        paired = {
            "master": {"s1": {"a"}, "s2": {"a"}},
            "pr-1": {"s1": {"a", "b"}, "s2": {"a", "c"}},
        }
        unpaired = {
            "master": {"m1": {"a"}, "m2": {"a"}},
            "pr-1": {"p1": {"a", "b"}, "p2": {"a", "c"}},
        }
        paired_summary = analyze.build_differential_coverage_summary_rows(
            "by_target/paired", analyze.calculate_relscores(paired), analyze.calculate_relcovs(paired)
        )
        unpaired_summary = analyze.build_differential_coverage_summary_rows(
            "by_target/unpaired", analyze.calculate_relscores(unpaired), analyze.calculate_relcovs(unpaired)
        )
        paired_rows, _ = analyze.build_sequential_state_rows(
            paired_summary, {"by_target/paired": paired}
        )
        unpaired_rows, _ = analyze.build_sequential_state_rows(
            unpaired_summary, {"by_target/unpaired": unpaired}
        )
        self.assertTrue(paired_rows[0]["paired"])
        self.assertEqual(paired_rows[0]["test_name"], "paired-sign")
        self.assertFalse(unpaired_rows[0]["paired"])
        self.assertEqual(unpaired_rows[0]["test_name"], "mann-whitney-u-normal-approx")

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

    def test_skips_large_by_test_campaigns_but_keeps_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap_root = root / "logs" / "i-live" / "showmap"
            for approach in ("foundry-master", "foundry-candidate"):
                showmap_dir = showmap_root / f"{approach}__Suite"
                showmap_dir.mkdir(parents=True)
                (showmap_dir / "trial-1.txt").write_text(
                    "a:1\nb:1\nc:1\n",
                    encoding="utf-8",
                )

            out_dir = root / "out"
            analyze.write_differential_coverage_outputs(
                root / "logs",
                out_dir,
                max_work_items=1,
            )

            with (out_dir / "differential_coverage_relscores.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                sorted({row["campaign"] for row in rows}),
                ["combined"],
            )

            manifest = json.loads(
                (out_dir / "showmap_campaign_manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "skipped_analysis",
                manifest["campaigns"]["by_test/Suite"],
            )
            self.assertNotIn(
                "skipped_analysis",
                manifest["campaigns"]["combined"],
            )


if __name__ == "__main__":
    unittest.main()
