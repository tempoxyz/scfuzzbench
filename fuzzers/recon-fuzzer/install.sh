#!/usr/bin/env bash
set -euo pipefail

source /opt/scfuzzbench/common.sh

prepare_workspace
install_base_packages
install_foundry
install_crytic_compile
install_slither_analyzer

require_env RECON_VERSION
recon_version="${RECON_VERSION#v}"
log "Installing Recon fuzzer v${recon_version}"

tmp_dir=$(mktemp -d)
archive="recon-linux-x86_64.tar.gz"
url="https://github.com/Recon-Fuzz/recon-fuzzer/releases/download/v${recon_version}/${archive}"

sha256="${RECON_SHA256:-}"
if [[ -z "${sha256}" && "${recon_version}" == "0.4.6" ]]; then
  sha256="36c33e6acdb6b9225f20ca8436dc4bd25767c9649a31f90fba0da8e94f596be5"
fi
download_verified "${url}" "${tmp_dir}/${archive}" "${sha256}"
tar -xzf "${tmp_dir}/${archive}" -C "${tmp_dir}"

bin_path=$(find "${tmp_dir}" -type f -name "recon" | head -n 1)
if [[ -z "${bin_path}" ]]; then
  log "recon binary not found in archive"
  exit 1
fi
install -m 0755 "${bin_path}" /usr/local/bin/recon

rm -rf "${tmp_dir}"

command -v recon
recon --version || true
