# Security Policy

## Supported versions

Only the latest version on the `main` branch is supported.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting for this repository, or contact the maintainer through the repository owner's GitHub profile. Include a clear reproduction case, affected version, impact, and any suggested mitigation.

Reports are acknowledged within 14 days. After a fix is available, the maintainer will coordinate disclosure with the reporter.

## Security design

ColorSSH is a local-only terminal application. It makes no network requests, has no third-party Python dependencies, and does not execute shell content from preset files. It writes changes only after validating Bash syntax, detecting concurrent changes, creating a backup, and atomically replacing the selected file.

The application must be run as a normal user. It does not support editing privileged shell files. Backups and saved presets are stored with owner-only permissions in `~/.config/colorssh`.
