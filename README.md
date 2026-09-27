# scfuzzbench

Benchmark suite for smart-contract fuzzers.

🚀 **Support us on TheDAO Security Fund! https://giveth.io/project/scfuzzbench:-smart-contract-fuzzer-benchmark-suite**


<table>
  <tr>
    <td><img src="docs/public/images/sample-run/bugs_over_time.png" alt="Bugs over time" width="420"></td>
    <td><img src="docs/public/images/sample-run/time_to_k.png" alt="Time to k" width="420"></td>
  </tr>
  <tr>
    <td><img src="docs/public/images/sample-run/final_distribution.png" alt="Final distribution" width="420"></td>
    <td><img src="docs/public/images/sample-run/plateau_and_late_share.png" alt="Plateau and late share" width="420"></td>
  </tr>
</table>

## Motivation

- Maintain a current view of common fuzzers under a shared, realistic workload.
- Focus on benchmark quality with real projects, real bug-finding tasks, long timeouts, and repeated runs.
- Publish transparent metrics and artifacts for independent review.
- Help fuzzer/tool builders identify bottlenecks and improve their tools.

## Inclusion Criteria For Fuzzers

A fuzzer is currently considered in-scope when it is:

- Open source.
- Able to run assertion failures.
- Able to run global invariants.

## Fuzzers Currently Ready

- Foundry
- Echidna
- Medusa
- Recon Fuzzer

## Benchmark Targets

- [Aave v4](https://github.com/Recon-Fuzz/aave-v4-scfuzzbench)
- [Superform v2-periphery](https://github.com/Recon-Fuzz/superform-v2-periphery-scfuzzbench)
- [Liquity v2 Governance](https://github.com/Recon-Fuzz/liquity-V2-gov-scfuzzbench)
- [Nerite](https://github.com/Recon-Fuzz/nerite-scfuzzbench)

Use the target onboarding skill for new targets:

- `skills/README.md`
- `skills/target-onboarding/SKILL.md`

## Documentation

For all technical/operational details, use the docs site pages:

- Introduction: `docs/introduction.md`
- Start benchmark request: `docs/start.md`
- Methodology: `docs/methodology.md`
- Operations guide (Terraform, running, reruns, analysis, CI workflows): `docs/operations.md`
- Target onboarding skill (machine-oriented): `skills/target-onboarding/SKILL.md`

Rendered docs navigation and run/benchmark pages are available under `docs/`.

## Dependency maintenance

Use Node.js 24 and npm 11.19 or newer for the docs site. `npm ci` installs the
locked dependencies with lifecycle scripts disabled; `npm run docs:build` checks
the site. VitePress is pinned to `2.0.0-alpha.20` because the latest 1.x release
still depends on vulnerable Vite/esbuild versions. No dependency overrides are used.

The analysis environment requires Python 3.11 or newer. Edit
`analysis/requirements.in`, then regenerate the pinned, hashed requirements:

```sh
uv pip compile analysis/requirements.in --python-version 3.11 --no-build \
  --exclude-newer 7d --generate-hashes --upgrade -o analysis/requirements.txt
uv run --python 3.11 --no-build --with-requirements analysis/requirements.txt \
  python -m unittest discover -s analysis/tests
```

Fuzzer release archives are verified before extraction. The default Echidna,
Medusa, Recon, and binary Foundry versions have SHA-256 digests pinned in their
installers. When selecting another version, provide its verified `ECHIDNA_SHA256`,
`MEDUSA_SHA256`, `RECON_SHA256`, or `FOUNDRY_SHA256` using the existing fuzzer
environment map (or environment variables for local runs). Obtain the digest from
the upstream release and review it before running; a missing or mismatched digest
fails installation. Foundry source builds continue to use the requested Git ref
and `cargo build --locked`.
