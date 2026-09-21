# ColorSSH

ColorSSH is a local RGB and HSV editor for the Bash terminal, prompt, and GNU `ls` file colors. It uses only Python's standard library and Bash.

It displays all 20 colors in one palette, provides live terminal previews, includes built-in themes, and keeps backups before changing a shell file.

## Requirements

- Linux or WSL
- Python 3.7 or newer
- Bash
- GNU coreutils (`ls`)
- A 24-bit RGB terminal with at least 80 columns and 32 rows

## Install

Clone the repository, inspect the release you intend to run, then launch the installer as a normal user:

```bash
git clone https://github.com/SISRASP/colorssh.git
cd colorssh
sh install.sh
colorssh
```

The installer checks for Python, Bash, and GNU coreutils. When needed, it uses your distribution's package manager (`apt`, `dnf`, `yum`, `pacman`, `zypper`, or `apk`) and requests `sudo` only for system package installation and copying the program to `/usr/local/bin`. It does not use `pip`, modify `.bashrc`, or read network content itself.

You may also download a source archive from GitHub and run `sh install.sh` from the extracted directory. To run directly from a checkout when the requirements are already available:

```bash
./colorssh
```

If `/usr/local/bin` is not in your `PATH`, run `/usr/local/bin/colorssh`.

## Use

Run `colorssh` from an interactive Bash terminal. Do not run the application with `sudo`.

- Up/Down selects a color; Tab selects a channel.
- Left/Right adjusts a channel by one; `+`/`-` adjusts it by ten; Home/End set minimum/maximum.
- `M` switches between RGB and HSV controls.
- `S` applies the current palette to the selected Bash file.
- `R` restores the colors loaded or last saved in the current session.
- `N` or `G` saves a named theme; `C` opens the theme selector.
- `Q` exits. Press it twice when there are unsaved edits.

Use `--bashrc /path/to/file` to select a Bash file other than `~/.bashrc`, and `--presets /path/to/file.json` to use a separate theme file. Only select files you own and trust.

After saving, run `source ~/.bashrc` in Bash or open a new terminal. A child application cannot update its parent shell.

## What it changes

ColorSSH appends a marked block to the selected Bash file and updates that same block on later saves. The block sets OSC 10/11 terminal colors, `PS1`, `LS_COLORS`, and the `ll` alias. Existing `LS_COLORS` extension rules are preserved and retain priority.

Before every change, ColorSSH creates a timestamped backup in `~/.config/colorssh`. That directory, saved themes, and backups are owner-only. It validates the generated file with `bash -n`, detects external changes, and writes the replacement atomically.

Built-in themes include Classic Dark, Dracula, Nord, Monokai, Gruvbox Dark, Solarized Dark, Tokyo Night, One Dark, Classic Light, Solarized Light, Deep Ocean, Night Forest, Retro Amber, Space Violet, Roasted Coffee, Urban Neon, Cream Paper, Light Lavender, Soft Mint, Polar Ice, and Claude.

## Restore and uninstall

Back up your current `.bashrc` first, then restore the desired timestamped backup from `~/.config/colorssh`. Alternatively, remove the block between `# >>> colorssh >>>` and `# <<< colorssh <<<` manually.

To remove the installed executable:

```bash
sudo rm /usr/local/bin/colorssh
```

This does not remove your saved themes or backups.

## Troubleshooting

- If `~/.bashrc` does not exist, create it with `touch ~/.bashrc`, or pass `--bashrc` with an existing file.
- If colors do not appear after saving, run `source ~/.bashrc` in Bash and confirm that the terminal supports 24-bit RGB. `tmux` and `screen` can filter OSC 10/11 sequences.
- If the terminal is too small, enlarge it to at least 80 × 32.
- If a save reports an external change, restart ColorSSH so it loads the current file before saving.
- If dependency installation fails, check your distribution's package repositories and network connection, then run the installer again.

## Security

ColorSSH has no network features and no third-party runtime dependencies. Read [SECURITY.md](SECURITY.md) for the vulnerability reporting process and security properties. Please inspect the code before granting `sudo` to any installer.

## Development

```bash
sh -n install.sh
python3 -m unittest discover -s tests -v
```

Tests use temporary files and pseudoterminals. They do not run the installer or require administrator permissions. Contribution guidelines are in [CONTRIBUTING.md](CONTRIBUTING.md). This project is released under the [MIT License](LICENSE).
