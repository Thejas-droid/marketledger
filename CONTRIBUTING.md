# Contributing

Use a feature branch and keep changes focused. Explain the behavior being changed,
provide a small input example when relevant, and include validation results.

Build and run the regression suite:

```sh
python tools/build.py --test
python -m unittest discover -s tests -p test_tools.py -v
```

For MSVC, use the CMake instructions in the README. Run ASan/UBSan on a supported
Linux compiler when changing memory ownership or matching logic:

```sh
python tools/build.py --sanitize --test
```

New matching behavior must preserve conservation of units and cash. Keep the
independent reference matcher independent of the production implementation.
Document changes to CSV schemas, priority, expiry, or CLI options.

Do not commit credentials, account data, generated binaries, or
third-party market data. Retain the MIT license and provenance notice.
