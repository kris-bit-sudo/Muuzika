# Security

Do not post passwords, tokens, personal server URLs or player_data.json in
public issues. Report ordinary UI defects using the bug template.

Before publishing, the maintainer should enable GitHub private vulnerability
reporting under repository Settings > Security. Until a private reporting route
exists, do not publish exploit details or credentials in an issue.

TLS verification is enabled by default. Library synchronization is explicit.
Uncached tracks download when played. Credentials use the Windows keyring when
available; tests disable credentials and block network requests.

This beta is unsigned and has not received an independent security audit.
