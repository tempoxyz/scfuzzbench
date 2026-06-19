# Start Benchmark

This page creates a **benchmark request** issue in GitHub.

Need a new target first? Use the target onboarding skill at
[`skills/target-onboarding/SKILL.md`](https://github.com/Recon-Fuzz/scfuzzbench/blob/main/skills/target-onboarding/SKILL.md)
and follow its workflow.

The request moves through GitHub labels:

- `benchmark/01-pending`: added by the issue template on creation.
- `benchmark/02-validated`: added by the bot after JSON validation passes.
- `benchmark/03-approved`: added manually by a maintainer.

Use the preconfigured target selector to auto-fill target repo/commit for the current benchmark targets listed in `README.md`.

Current preconfigured targets:

- Aave v4 (`0xalpharush/aave-v4-scfuzzbench@262c55ab1f147cc6205568ac1f0c60378eb38222`, from `fix`)
- Superform v2-periphery (`Recon-Fuzz/superform-v2-periphery-scfuzzbench@29acf9fb679981ae984cab7d2f268e386fa88653`, from `dev-recon`)
- Liquity v2 Governance (`Recon-Fuzz/liquity-V2-gov-scfuzzbench@42212075645e4fc7bc46714e3f14582a06181560`, from `recon`)
- Nerite (`Recon-Fuzz/nerite-scfuzzbench@205c8a8e40fe45217c97bd75fb692aac8ecc2579`, from `dev-recon`)

Foundry PR CI should use the minimum matrix first: deterministically select 2 of
the 4 pinned targets, run 2 rounds per target per side, and aggregate the median
differential coverage summary. Confirmation runs expand to all 4 targets and 3
rounds; the initially selected 2 targets reuse their first 2 rounds and run only
one additional round.

<StartBenchmark />

::: warning
Do not put secrets in the issue body. The request is intentionally public/auditable.
:::
