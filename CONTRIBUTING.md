# Contributing

Contributions are welcome. Please open an issue before making a large change so the scope can be discussed.

## Development

The project requires Python 3.7 or newer, Bash, and GNU coreutils. It has no Python packages to install.

```bash
sh -n install.sh
python3 -m unittest discover -s tests -v
```

Keep changes small, add or update tests for behavior changes, and do not commit generated files, credentials, personal configuration, or backup files. The application must continue to work with only the Python standard library.

## Pull requests

Describe the problem, the proposed behavior, and how you tested it. Do not include unrelated formatting changes. Security-sensitive fixes should follow the private reporting process in [SECURITY.md](SECURITY.md) first.
