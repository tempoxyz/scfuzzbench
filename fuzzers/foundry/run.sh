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

run_with_samply_timeout() {
  require_env SCFUZZBENCH_TIMEOUT_SECONDS FOUNDRY_SAMPLY_DIR
  local log_file=$1
  shift
  local run_start
  run_start=$(now_epoch_seconds)
  local kill_after="${SCFUZZBENCH_TIMEOUT_GRACE_SECONDS:-300}"
  if [[ ! "${kill_after}" =~ ^[0-9]+$ ]]; then
    kill_after=300
  fi

  mkdir -p "${FOUNDRY_SAMPLY_DIR}"
  local -a samply_args=(--save-only --presymbolicate --output "${FOUNDRY_SAMPLY_DIR}/profile-foundry.json.gz")
  if [[ -n "${FOUNDRY_SAMPLY_ARGS:-}" ]]; then
    local -a configured_samply_args
    read -r -a configured_samply_args <<< "${FOUNDRY_SAMPLY_ARGS}"
    samply_args=("${configured_samply_args[@]}" "${samply_args[@]}")
  fi

  # Keep samply outside the benchmark timeout process group so it can flush the
  # profile after timeout interrupts forge.
  local -a timed_cmd=(timeout --signal=SIGINT --kill-after="${kill_after}s" "${SCFUZZBENCH_TIMEOUT_SECONDS}s" "$@")
  append_runner_command_log "${SCFUZZBENCH_TIMEOUT_SECONDS}" "${kill_after}" samply record "${samply_args[@]}" "${timed_cmd[@]}" || true
  log "Running command under samply with timeout ${SCFUZZBENCH_TIMEOUT_SECONDS}s (grace ${kill_after}s)"
  set +e
  samply record "${samply_args[@]}" "${timed_cmd[@]}" 2>&1 | tee "${log_file}"
  local exit_code=${PIPESTATUS[0]}
  set -e
  log_duration "run_with_samply_timeout $(basename "${log_file}")" "${run_start}"
  if [[ "${exit_code}" -eq 124 ]]; then
    log "Command reached configured benchmark timeout; treating as completed run"
    return 0
  fi
  return ${exit_code}
}

repo_dir="${SCFUZZBENCH_WORKDIR}/target"
log_file="${SCFUZZBENCH_LOG_DIR}/foundry.log"
default_corpus_dir="${repo_dir}/corpus/foundry"
corpus_dir="${FOUNDRY_CORPUS_DIR:-${default_corpus_dir}}"
if [[ "${corpus_dir}" != /* ]]; then
  corpus_dir="${repo_dir}/${corpus_dir}"
fi
export SCFUZZBENCH_CORPUS_DIR="${corpus_dir}"
mkdir -p "${SCFUZZBENCH_CORPUS_DIR}"

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

forge_cmd=(forge test --mc CryticToFoundry)
if ((${#extra_args[@]})); then
  forge_cmd+=("${extra_args[@]}")
fi

set +e
pushd "${repo_dir}" >/dev/null
exit_code=0
if [[ -n "${FOUNDRY_SAMPLY_DIR:-}" ]]; then
  run_with_samply_timeout "${log_file}" "${forge_cmd[@]}" || exit_code=$?
else
  run_with_timeout "${log_file}" "${forge_cmd[@]}" || exit_code=$?
fi

showmap_enabled="${SCFUZZBENCH_FOUNDRY_SHOWMAP:-1}"
showmap_enabled_lc=$(printf '%s' "${showmap_enabled}" | tr '[:upper:]' '[:lower:]')
if [[ "${showmap_enabled}" == "1" || "${showmap_enabled_lc}" == "true" || "${showmap_enabled_lc}" == "yes" ]]; then
  showmap_dir="${SCFUZZBENCH_LOG_DIR}/showmap"
  showmap_log_file="${SCFUZZBENCH_LOG_DIR}/foundry_showmap.log"
  showmap_trial="${SCFUZZBENCH_RUN_ID:-${SCFUZZBENCH_INSTANCE_ID:-$(hostname)}}"
  # Do NOT default --showmap-corpus-dir to SCFUZZBENCH_CORPUS_DIR. For invariant
  # tests forge persists the corpus under a per-contract subdir of the configured
  # `[invariant] corpus_dir` (e.g. `corpus/foundry/<Contract>`), and when
  # --showmap-corpus-dir is omitted the showmap replay resolves that same
  # per-test path from config. Passing the un-nested base dir here makes the
  # replay read an empty directory ("replay: 0 entries, 0 files"), which yields
  # empty showmap coverage and an empty differential-coverage report. Only honor
  # an explicit FOUNDRY_SHOWMAP_CORPUS_DIR override.
  showmap_corpus_dir="${FOUNDRY_SHOWMAP_CORPUS_DIR:-}"
  showmap_args=(
    --showmap-out "${showmap_dir}"
    --showmap-approach "${SCFUZZBENCH_FUZZER_LABEL}"
    --showmap-trial "${showmap_trial}"
  )
  if [[ -n "${showmap_corpus_dir}" ]]; then
    showmap_args+=(--showmap-corpus-dir "${showmap_corpus_dir}")
  fi
  if [[ -n "${FOUNDRY_SHOWMAP_DOMAIN:-}" ]]; then
    showmap_args=(--showmap-domain "${FOUNDRY_SHOWMAP_DOMAIN}" "${showmap_args[@]}")
  fi
  mkdir -p "${showmap_dir}"
  original_timeout="${SCFUZZBENCH_TIMEOUT_SECONDS:-}"
  showmap_timeout="${SCFUZZBENCH_FOUNDRY_SHOWMAP_TIMEOUT_SECONDS:-}"
  if [[ -z "${showmap_timeout}" ]]; then
    showmap_timeout=1800
    if [[ "${original_timeout}" =~ ^[0-9]+$ ]] && [[ "${original_timeout}" -gt 0 ]] && [[ "${original_timeout}" -lt "${showmap_timeout}" ]]; then
      showmap_timeout="${original_timeout}"
    fi
  fi
  SCFUZZBENCH_TIMEOUT_SECONDS="${showmap_timeout}"
  replay_extra_args=()
  skip_showmap_arg_value=0
  if ((${#extra_args[@]})); then
    for arg in "${extra_args[@]}"; do
      if [[ "${skip_showmap_arg_value}" -eq 1 ]]; then
        skip_showmap_arg_value=0
        continue
      fi
      case "${arg}" in
        --showmap-out|--showmap-approach|--showmap-trial|--showmap-corpus-dir|--showmap-domain)
          skip_showmap_arg_value=1
          ;;
        --showmap-out=*|--showmap-approach=*|--showmap-trial=*|--showmap-corpus-dir=*|--showmap-domain=*)
          ;;
        *)
          replay_extra_args+=("${arg}")
          ;;
      esac
    done
  fi
  showmap_cmd=(forge test --mc CryticToFoundry)
  if ((${#replay_extra_args[@]})); then
    showmap_cmd+=("${replay_extra_args[@]}")
  fi
  showmap_cmd+=("${showmap_args[@]}")
  run_with_timeout "${showmap_log_file}" "${showmap_cmd[@]}" || \
    log "Foundry showmap replay failed; continuing with original forge test exit code ${exit_code}."
  if [[ -n "${original_timeout}" ]]; then
    SCFUZZBENCH_TIMEOUT_SECONDS="${original_timeout}"
  fi
fi
popd >/dev/null
set -e

upload_results

if [[ -n "${FOUNDRY_SAMPLY_DIR:-}" ]]; then
  comment_file="${FOUNDRY_SAMPLY_DIR}/comment.md"
  {
    echo "## Samply profiles"
    echo
    echo "Foundry invariant benchmark CPU profiles were captured with samply."
    echo
    shopt -s nullglob
    profiles=("${FOUNDRY_SAMPLY_DIR}"/profile-*.json.gz)
    if [[ "${#profiles[@]}" -eq 0 ]]; then
      echo "_No samply profile files were produced._"
    else
      for profile in "${profiles[@]}"; do
        echo "- \`$(basename "${profile}")\`"
      done
    fi
  } > "${comment_file}"
fi

exit ${exit_code}
