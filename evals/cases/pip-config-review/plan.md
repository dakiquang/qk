# Fix fatal config set error

Address pip issue #13279: allow configuration changes through the file named by
`PIP_CONFIG_FILE` and provide a helpful message explaining where changes are
written. Preserve configuration file selection behavior and add functional
coverage for configuration operations with an environment-selected file.

Scope: configuration management, its functional tests, and a bugfix news entry.
