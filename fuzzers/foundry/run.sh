#!/usr/bin/env bash
set -euo pipefail

source "${SCFUZZBENCH_COMMON_SH:-/opt/scfuzzbench/common.sh}"

register_shutdown_trap

prepare_workspace
if [[ -z "${HOME:-}" ]]; then
  export HOME=/root
fi
export PATH="${HOME}/.foundry/bin:${PATH}"

if [[ -n "${FOUNDRY_LABEL:-}" ]]; then
  SCFUZZBENCH_FUZZER_LABEL="${FOUNDRY_LABEL}"
elif [[ -f "${SCFUZZBENCH_ROOT:-/opt/scfuzzbench}/foundry_commit" ]]; then
  foundry_commit=$(cat "${SCFUZZBENCH_ROOT:-/opt/scfuzzbench}/foundry_commit")
  SCFUZZBENCH_FUZZER_LABEL="foundry-git-${foundry_commit}"
else
  require_env FOUNDRY_VERSION
  SCFUZZBENCH_FUZZER_LABEL="foundry-${FOUNDRY_VERSION}"
fi
export SCFUZZBENCH_FUZZER_LABEL

clone_target
apply_benchmark_type
build_target

repo_dir="${SCFUZZBENCH_WORKDIR}/target"
log_file="${SCFUZZBENCH_LOG_DIR}/foundry.log"

extra_args=()
if [[ -n "${FOUNDRY_TEST_ARGS:-}" ]]; then
  read -r -a extra_args <<< "${FOUNDRY_TEST_ARGS}"
fi

set_default_worker_env FOUNDRY_THREADS
if [[ -n "${FOUNDRY_THREADS:-}" ]]; then
  has_threads_arg=0
  for arg in "${extra_args[@]}"; do
    case "${arg}" in
      --threads|--jobs|-j|--threads=*|--jobs=*|-j*)
        has_threads_arg=1
        break
        ;;
    esac
  done
  if [[ "${has_threads_arg}" -eq 0 ]]; then
    extra_args=(--threads "${FOUNDRY_THREADS}" "${extra_args[@]}")
  fi
fi

set +e
pushd "${repo_dir}" >/dev/null
run_with_timeout "${log_file}" forge test --mc CryticToFoundry "${extra_args[@]}"
exit_code=$?

showmap_enabled="${SCFUZZBENCH_FOUNDRY_SHOWMAP:-1}"
if [[ "${showmap_enabled}" == "1" || "${showmap_enabled,,}" == "true" || "${showmap_enabled,,}" == "yes" ]]; then
  showmap_dir="${SCFUZZBENCH_LOG_DIR}/showmap"
  showmap_log_file="${SCFUZZBENCH_LOG_DIR}/foundry_showmap.log"
  showmap_trial="${SCFUZZBENCH_RUN_ID:-${SCFUZZBENCH_INSTANCE_ID:-$(hostname)}}"
  showmap_corpus_dir="${FOUNDRY_SHOWMAP_CORPUS_DIR:-${SCFUZZBENCH_CORPUS_DIR:-}}"
  if [[ -z "${showmap_corpus_dir}" ]]; then
    showmap_corpus_dir="${repo_dir}/corpus/foundry"
  fi
  showmap_args=(
    --showmap-out "${showmap_dir}"
    --showmap-approach "${SCFUZZBENCH_FUZZER_LABEL}"
    --showmap-trial "${showmap_trial}"
    --showmap-corpus-dir "${showmap_corpus_dir}"
  )
  if [[ -n "${FOUNDRY_SHOWMAP_DOMAIN:-}" ]]; then
    showmap_args=(--showmap-domain "${FOUNDRY_SHOWMAP_DOMAIN}" "${showmap_args[@]}")
  fi
  mkdir -p "${showmap_dir}"
  run_with_timeout "${showmap_log_file}" forge test --mc CryticToFoundry "${showmap_args[@]}" || \
    log "Foundry showmap replay failed; continuing with original forge test exit code ${exit_code}."
fi
popd >/dev/null
set -e

upload_results
exit ${exit_code}
