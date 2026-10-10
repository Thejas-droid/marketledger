# Security

Market Ledger 1.0 is an offline research simulator. It does not accept credentials,
connect to a broker, or execute real trades. Run it with local files you trust.

CSV inputs are validated for identifier syntax, numeric ranges, field counts,
event count, timestamp order, and duplicate order IDs. Inputs are limited to
10,000 events and 4,096 bytes per line; this is a bounded research application,
not an exposed service for hostile uploads. HTML reports escape embedded data.

If you find a vulnerability, use the repository's GitHub private vulnerability
reporting feature if enabled. Otherwise open an issue requesting a private contact
without publishing exploit details or sensitive files.

Only the latest release is maintained. There are no API keys or secrets required
by the application. The exporter's credential pattern check is a limited extra
check, not a guarantee that arbitrary added files contain no sensitive information.
