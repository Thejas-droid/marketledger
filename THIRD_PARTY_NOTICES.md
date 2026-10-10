# Third-party notices

Market Ledger is maintained and presented by [thejas-droid](https://github.com/thejas-droid).

The upstream MIT copyright notice is retained in `LICENSE`:
Copyright (c) 2023 sakshamrathi21. Keep the copyright notice and permission text
with redistributions covered by that license.

Market Ledger includes its own portable simulator implementation, public interface,
synthetic datasets, test suite, reporting tools, and release workflow.

The runtime uses only the C++ standard library. Build, test, export, and report
tools use the Python standard library. There are no bundled third-party runtime
packages, market datasets, brand assets, or remote fonts.

GitHub Actions references `actions/checkout` and `actions/setup-python`; these
run in GitHub's CI environment and are not bundled into the application.
