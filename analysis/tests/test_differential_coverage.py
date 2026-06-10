import tempfile
import unittest
from pathlib import Path

from analysis import analyze


class DifferentialCoverageTests(unittest.TestCase):
    def test_calculates_relscores_from_showmap_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs" / "i-a-foundry" / "showmap" / "foundry").mkdir(
                parents=True
            )
            (root / "logs" / "i-a-foundry" / "showmap" / "echidna").mkdir()
            (root / "logs" / "i-a-foundry" / "showmap" / "foundry" / "t1.txt").write_text(
                "1:1\n2:1\n", encoding="utf-8"
            )
            (root / "logs" / "i-a-foundry" / "showmap" / "foundry" / "t2.txt").write_text(
                "1:1\n3:1\n", encoding="utf-8"
            )
            (root / "logs" / "i-a-foundry" / "showmap" / "echidna" / "t1.txt").write_text(
                "1:1\n", encoding="utf-8"
            )

            out_csv = root / "out" / "differential_coverage_relscores.csv"
            analyze.write_differential_coverage_relscores_csv(root / "logs", out_csv)

            rows = out_csv.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                rows,
                [
                    "campaign,approach,relscore,trials,covered_edges",
                    "i-a-foundry/showmap,foundry,1.000000,2,3",
                    "i-a-foundry/showmap,echidna,0.000000,1,1",
                ],
            )

    def test_ignores_single_approach_campaigns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            showmap = root / "logs" / "i-a-foundry" / "showmap" / "foundry"
            showmap.mkdir(parents=True)
            (showmap / "t1.txt").write_text("1:1\n", encoding="utf-8")

            out_csv = root / "out" / "differential_coverage_relscores.csv"
            analyze.write_differential_coverage_relscores_csv(root / "logs", out_csv)

            self.assertEqual(
                out_csv.read_text(encoding="utf-8").strip(),
                "campaign,approach,relscore,trials,covered_edges",
            )


if __name__ == "__main__":
    unittest.main()
