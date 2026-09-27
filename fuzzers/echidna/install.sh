#!/usr/bin/env bash
set -euo pipefail

source "${SCFUZZBENCH_COMMON_SH:-/opt/scfuzzbench/common.sh}"

prepare_workspace
install_base_packages
install_foundry
install_crytic_compile
install_slither_analyzer

require_env ECHIDNA_VERSION
log "Installing Echidna ${ECHIDNA_VERSION}"

tmp_dir=$(mktemp -d)
archive="echidna-${ECHIDNA_VERSION}-x86_64-linux.tar.gz"
url="https://github.com/crytic/echidna/releases/download/v${ECHIDNA_VERSION}/${archive}"

sha256="${ECHIDNA_SHA256:-}"
if [[ -z "${sha256}" && "${ECHIDNA_VERSION}" == "2.3.1" ]]; then
  sha256="64a7d65a0bea6051f76f551d9838f6f8e82148436929468224e1fdda268fd51d"
fi
download_verified "${url}" "${tmp_dir}/${archive}" "${sha256}"
mkdir -p "${tmp_dir}/echidna"
tar -xzf "${tmp_dir}/${archive}" -C "${tmp_dir}/echidna"

bin_path=$(find "${tmp_dir}/echidna" -type f \( -name "echidna-test" -o -name "echidna" \) | head -n 1)
if [[ -z "${bin_path}" ]]; then
  log "echidna binary not found in archive"
  exit 1
fi
install -m 0755 "${bin_path}" "${SCFUZZBENCH_BIN_DIR}/echidna-test"

rm -rf "${tmp_dir}"

command -v echidna-test
