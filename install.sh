#!/bin/sh
# Instalador para Linux. Ejecutar como usuario normal; solicita sudo si hace falta.
set -eu
PATH=/usr/bin:/bin
export PATH

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
    -h|--help)
        printf 'Uso: sh install.sh\nInstala Python 3, Bash y GNU coreutils si faltan, y enlaza ColorSSH en /usr/local/bin.\n'
        exit 0 ;;
    '') ;;
    *) fail "Argumento desconocido: $1. Usa --help." ;;
esac
[ "$#" -le 1 ] || fail 'Demasiados argumentos.'
[ "$(uname -s)" = Linux ] || fail 'Este instalador admite Linux (incluido WSL).'

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
[ -f "$source_dir/colorssh" ] || fail 'Coloca install.sh junto al archivo colorssh.'

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo -- "$@"
    else
        fail 'Se necesitan permisos de administrador. Instala sudo o ejecuta este instalador como root.'
    fi
}

python_ok() {
    command -v python3 >/dev/null 2>&1 && python3 -c '
import sys
import argparse, copy, codecs, colorsys, datetime, json, os, pathlib, re
import select, shutil, signal, subprocess, tempfile, termios, tty, unicodedata
sys.exit(0 if sys.version_info >= (3, 7) else 1)
' >/dev/null 2>&1
}

gnu_ls_ok() {
    command -v ls >/dev/null 2>&1 && ls --version 2>/dev/null | grep -q 'GNU coreutils'
}

if ! python_ok || ! command -v bash >/dev/null 2>&1 || ! gnu_ls_ok || ! command -v install >/dev/null 2>&1; then
    printf 'Instalando dependencias del sistema…\n'
    if command -v apt-get >/dev/null 2>&1; then
        as_root apt-get update
        as_root apt-get install -y python3 bash coreutils
    elif command -v dnf >/dev/null 2>&1; then
        as_root dnf install -y python3 bash coreutils
    elif command -v yum >/dev/null 2>&1; then
        as_root yum install -y python3 bash coreutils
    elif command -v pacman >/dev/null 2>&1; then
        as_root pacman -S --needed --noconfirm python bash coreutils
    elif command -v zypper >/dev/null 2>&1; then
        as_root zypper --non-interactive install python3 bash coreutils
    elif command -v apk >/dev/null 2>&1; then
        as_root apk add python3 bash coreutils
    else
        fail 'Gestor de paquetes no compatible. Instala Python >= 3.7, Bash y GNU coreutils y vuelve a ejecutar el instalador.'
    fi
fi

python_ok || fail 'Se necesita Python >= 3.7 con su biblioteca estándar. Actualiza Python y vuelve a intentarlo.'
command -v bash >/dev/null 2>&1 || fail 'No se encuentra Bash en PATH.'
gnu_ls_ok || fail 'No se encuentra GNU ls en PATH.'
command -v install >/dev/null 2>&1 || fail 'No se encuentra install en PATH.'
python3 "$source_dir/colorssh" --help >/dev/null

as_root install -d -m 755 /usr/local/bin
chmod 755 "$source_dir/colorssh"
as_root ln -sf "$source_dir/colorssh" /usr/local/bin/colorssh
/usr/local/bin/colorssh --help >/dev/null

printf '\nColorSSH enlazado en /usr/local/bin/colorssh\n'
case ":$PATH:" in
    *:/usr/local/bin:*) printf 'Para abrirlo: colorssh\n' ;;
    *) printf 'Para abrirlo: /usr/local/bin/colorssh\n' ;;
esac
printf 'Ejecuta la aplicación como usuario normal, en una terminal RGB de al menos 80 × 32.\n'
printf 'Si tu shell habitual no es Bash, abre bash antes de usarla.\n'
