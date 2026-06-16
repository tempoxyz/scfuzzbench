import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "fuzzers" / "foundry" / "run.sh"


class FoundryRunShowmapArgsTests(unittest.TestCase):
    def test_showmap_replay_keeps_test_args_but_uses_script_showmap_args(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            log_dir = tmp_dir / "logs"
            work_dir = tmp_dir / "work"
            common_sh = tmp_dir / "common.sh"
            common_sh.write_text(
                """
register_shutdown_trap() { :; }
prepare_workspace() { mkdir -p "${SCFUZZBENCH_WORKDIR}/target" "${SCFUZZBENCH_LOG_DIR}"; }
clone_target() { :; }
apply_benchmark_type() { :; }
build_target() { :; }
set_default_worker_env() { :; }
log() { printf '%s\n' "$*" >> "${SCFUZZBENCH_LOG_DIR}/log.txt"; }
upload_results() { :; }
run_with_timeout() {
  {
    printf 'RUN'
    for arg in "$@"; do printf '\t%s' "$arg"; done
    printf '\n'
  } >> "${SCFUZZBENCH_LOG_DIR}/commands.tsv"
  return 0
}
""",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "SCFUZZBENCH_COMMON_SH": str(common_sh),
                    "SCFUZZBENCH_WORKDIR": str(work_dir),
                    "SCFUZZBENCH_LOG_DIR": str(log_dir),
                    "SCFUZZBENCH_RUN_ID": "bench-trial",
                    "SCFUZZBENCH_FOUNDRY_SHOWMAP": "1",
                    "FOUNDRY_LABEL": "foundry-master",
                    "FOUNDRY_TEST_ARGS": "--fork-url http://rpc --threads 3 --showmap-out /tmp/user-showmap --showmap-trial user-trial",
                }
            )

            subprocess.check_call(["bash", str(SCRIPT)], env=env)

            lines = (log_dir / "commands.tsv").read_text(encoding="utf-8").splitlines()
            commands = [line.split("\t") for line in lines]
            self.assertEqual(len(commands), 2)
            replay = commands[1]
            replay_args = replay[2:]

            self.assertEqual(replay[1], str(log_dir / "foundry_showmap.log"))
            self.assertIn("--fork-url", replay_args)
            self.assertIn("http://rpc", replay_args)
            self.assertIn("--threads", replay_args)
            self.assertIn("3", replay_args)
            self.assertNotIn("/tmp/user-showmap", replay_args)
            self.assertNotIn("user-trial", replay_args)

            showmap_out_idx = replay_args.index("--showmap-out")
            showmap_trial_idx = replay_args.index("--showmap-trial")
            self.assertEqual(replay_args[showmap_out_idx + 1], str(log_dir / "showmap"))
            self.assertEqual(replay_args[showmap_trial_idx + 1], "bench-trial")
            self.assertNotIn("--showmap-corpus-dir", replay_args)

    def test_showmap_replay_uses_explicit_corpus_override_only_when_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            log_dir = tmp_dir / "logs"
            work_dir = tmp_dir / "work"
            corpus_dir = tmp_dir / "seed-corpus"
            common_sh = tmp_dir / "common.sh"
            common_sh.write_text(
                """
register_shutdown_trap() { :; }
prepare_workspace() { mkdir -p "${SCFUZZBENCH_WORKDIR}/target" "${SCFUZZBENCH_LOG_DIR}"; }
clone_target() { :; }
apply_benchmark_type() { :; }
build_target() { :; }
set_default_worker_env() { :; }
log() { printf '%s\n' "$*" >> "${SCFUZZBENCH_LOG_DIR}/log.txt"; }
upload_results() { :; }
run_with_timeout() {
  {
    printf 'RUN'
    for arg in "$@"; do printf '\t%s' "$arg"; done
    printf '\n'
  } >> "${SCFUZZBENCH_LOG_DIR}/commands.tsv"
  return 0
}
""",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "SCFUZZBENCH_COMMON_SH": str(common_sh),
                    "SCFUZZBENCH_WORKDIR": str(work_dir),
                    "SCFUZZBENCH_LOG_DIR": str(log_dir),
                    "SCFUZZBENCH_RUN_ID": "bench-trial",
                    "SCFUZZBENCH_FOUNDRY_SHOWMAP": "1",
                    "FOUNDRY_LABEL": "foundry-master",
                    "FOUNDRY_SHOWMAP_CORPUS_DIR": str(corpus_dir),
                }
            )

            subprocess.check_call(["bash", str(SCRIPT)], env=env)

            lines = (log_dir / "commands.tsv").read_text(encoding="utf-8").splitlines()
            commands = [line.split("\t") for line in lines]
            replay_args = commands[1][2:]
            corpus_idx = replay_args.index("--showmap-corpus-dir")
            self.assertEqual(replay_args[corpus_idx + 1], str(corpus_dir))


if __name__ == "__main__":
    unittest.main()
