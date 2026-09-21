import copy
import importlib.machinery
import importlib.util
import json
import io
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('colorssh', str(ROOT / 'colorssh'))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class ColorsTest(unittest.TestCase):
    def setUp(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        env = patch.dict(os.environ, HOME=home.name)
        env.start()
        self.addCleanup(env.stop)

    def test_existing_prompt(self):
        text = r"PS1='${debian_chroot:+($debian_chroot)}\[\033[1;38;5;0;43m\]\u@\h:\w\$\[\033[00m\] '"
        self.assertEqual(m.load_colors(text)[2:4], [[0,0,0], [205,205,0]])

    def test_security_permissions_and_terminal_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.bashrc'
            path.write_text('# demo\n')
            path.chmod(0o644)
            _, backup = m.save_colors(path, path.read_bytes(), copy.deepcopy(m.DEFAULT))
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            self.assertEqual(backup.parent.stat().st_mode & 0o777, 0o700)
            preset_path = Path(directory)/'presets.json'
            m.write_presets(preset_path, {'Theme': copy.deepcopy(m.DEFAULT)})
            self.assertEqual(preset_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(m.display_text('safe\x1b[31m'), 'safe�[31m')

    def test_backup_repeat_and_shell_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.bashrc'
            original = b"# keep this\n__set_terminal_background_black() { :; }\nPROMPT_COMMAND=__set_terminal_background_black\nalias keep='echo preserved'\n"
            path.write_bytes(original)
            path.chmod(0o640)
            colors = copy.deepcopy(m.DEFAULT)
            colors[0] = [12,34,56]
            updated, backup = m.save_colors(path, original, colors)
            self.assertEqual(backup.parent, Path.home()/'.config'/'colorssh')
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            colors[2] = [87,65,43]
            updated2, backup2 = m.save_colors(path, updated, colors)
            self.assertNotEqual(backup, backup2)
            self.assertEqual(backup2.read_bytes(), updated)
            self.assertEqual(updated2.count(m.BEGIN.encode()), 1)
            self.assertTrue(updated2.startswith(original))
            self.assertEqual(m.load_colors(updated2.decode()), colors)
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                'TERM=xterm-256color; source "$1"; __set_terminal_background_black; printf "%s" "$PS1"; alias keep', 'bash', str(path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'\x1b]11;#0c2238\x07', result.stdout)
            self.assertIn(b'38;2;87;65;43', result.stdout)
            self.assertIn(b'echo preserved', result.stdout)

    def test_errors_leave_original_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.bashrc'
            original = b'# initial\n'
            path.write_bytes(original)
            with patch.object(m.shutil, 'copystat', side_effect=OSError('backup failed')):
                with self.assertRaises(OSError): m.save_colors(path, original, m.DEFAULT)
            self.assertEqual(path.read_bytes(), original)
            path.write_bytes(b'# external change\n')
            with self.assertRaises(ValueError): m.save_colors(path, original, m.DEFAULT)
            self.assertEqual(path.read_bytes(), b'# external change\n')
            for bad in (b'if then\n', (m.BEGIN+'\n').encode()):
                path.write_bytes(bad)
                with self.assertRaises(ValueError): m.save_colors(path, bad, m.DEFAULT)
                self.assertEqual(path.read_bytes(), bad)

    def test_legacy_colors_and_presets(self):
        import json
        legacy = copy.deepcopy(m.DEFAULT[:4])
        self.assertEqual(m.load_colors('# colorssh-colors: ' + json.dumps(legacy)), m.DEFAULT)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'config'/'presets.json'
            initial = m.load_presets(path)
            self.assertEqual(json.loads(path.read_text()), initial)
            self.assertEqual(len(initial), 21)
            self.assertTrue(all(m.valid_colors(colors) for colors in initial.values()))
            for name in ('Claro clásico', 'Solarizado claro'):
                self.assertTrue(all(channel > 220 for channel in initial[name][0]))
            initial['Dracula'][0][0] = 0
            self.assertNotEqual(initial['Dracula'], m.load_presets(path)['Dracula'])
            m.save_preset(path, 'Oscuro español', m.DEFAULT)
            alternate = copy.deepcopy(m.DEFAULT)
            alternate[5] = [12, 34, 56]
            m.save_preset(path, 'Claro', alternate)
            self.assertEqual(m.load_presets(path)['Oscuro español'], m.DEFAULT)
            self.assertEqual(m.load_presets(path)['Claro'], alternate)
            m.save_preset(path, 'Claro', m.DEFAULT)
            self.assertEqual(len(m.load_presets(path)), 23)
            m.save_preset(path, 'Dracula', alternate)
            self.assertEqual(m.load_presets(path)['Dracula'], alternate)
            path.write_text('{invalid')
            with self.assertRaises(ValueError):
                m.save_preset(path, 'Nuevo', m.DEFAULT)
            self.assertEqual(path.read_text(), '{invalid')

    def test_startup_materializes_presets_and_moves_old_backups(self):
        path = Path.home()/'.bashrc'
        path.write_text('# demo\n')
        old = path.with_name('.bashrc.bak.colorssh.20260921-110000')
        old.write_bytes(b'# old backup\n')
        destination = m.config_dir()
        destination.mkdir(parents=True)
        existing = destination/old.name
        existing.write_bytes(b'# different backup\n')
        with patch.dict(os.environ, XDG_CONFIG_HOME=str(Path.home()/'other')):
            app = m.App(path)
        self.assertEqual(app.presets_path, destination/'presets.json')
        self.assertEqual(json.loads(app.presets_path.read_text()), m.builtin_presets())
        self.assertFalse(old.exists())
        self.assertEqual(existing.read_bytes(), b'# different backup\n')
        self.assertIn(b'# old backup\n', [p.read_bytes() for p in destination.glob('.bashrc.bak.*')])
        app.act('n')
        for key in 'Personal': app.act(key)
        app.act('\r')
        self.assertIn('Personal', json.loads(app.presets_path.read_text()))
        m.App(path)
        self.assertEqual(len(list(destination.glob('.bashrc.bak.*'))), 2)

    def test_preset_ui_and_file_color_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.bashrc'
            path.write_text('# demo\n')
            app = m.App(path, Path(directory)/'presets.json')
            for _ in range(5): app.act('\x1b[B')
            self.assertEqual(app.target, 5)
            with patch.object(m.shutil, 'get_terminal_size', return_value=(100, 32)), patch('sys.stdout', new_callable=io.StringIO):
                app.draw()
            app.act('\x1b[<0;20;11M')
            self.assertEqual(app.target, 6)
            app.act('+')
            expected = copy.deepcopy(app.colors)
            app.act('n')
            for key in 'Mi combinación': app.act(key)
            app.act('\r')
            self.assertIsNone(app.mode)
            app.act('r')
            self.assertNotEqual(app.colors, expected)
            app.act('c')
            for _ in range(len(m.builtin_presets())): app.act('\x1b[B')
            app.act('\r')
            self.assertEqual(app.colors, expected)
            app.colors[0][0] = 123
            self.assertNotEqual(app.presets['Mi combinación'], app.colors)
            self.assertEqual(path.read_text(), '# demo\n')

    def test_real_ls_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'archivo').touch()
            (root/'carpeta').mkdir()
            (root/'ejecutable').touch()
            (root/'ejecutable').chmod(0o755)
            (root/'enlace').symlink_to('archivo')
            (root/'roto').symlink_to('missing')
            path = root/'.bashrc'
            path.write_text(m.config_block(m.DEFAULT))
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                'TERM=dumb; LS_COLORS="*.zip=31"; source "$1"; alias ll; '
                'printf "%s\n" "$LS_COLORS"; ls --color=always -d -- "$2"/*',
                'bash', str(path), str(root)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"alias ll='ls -alF --color=auto'", result.stdout)
            self.assertIn(b'*.zip=31', result.stdout)
            for color, name in [(m.DEFAULT[4], 'archivo'), (m.DEFAULT[5], 'carpeta'),
                                (m.DEFAULT[6], 'ejecutable'), (m.DEFAULT[7], 'enlace'),
                                (m.DEFAULT[8], 'roto')]:
                self.assertIn(('\x1b[0;38;2;' + ';'.join(map(str, color)) + 'm' +
                               str(root/name)).encode(), result.stdout)

    def test_dashboard_layout_preview_and_mouse(self):
        path = Path.home()/'.bashrc'
        path.write_text('# demo\n')
        app = m.App(path)
        for cols, rows in ((80, 32), (100, 32), (140, 45)):
            with self.subTest(cols=cols), patch.object(m.shutil, 'get_terminal_size', return_value=(cols, rows)):
                with patch('sys.stdout', new_callable=io.StringIO) as output:
                    app.draw()
                rendered = output.getvalue()
                for _, _, _, sample in m.FILE_TYPES:
                    self.assertIn(sample, rendered)
                self.assertIn('VISTA PREVIA', rendered)
                # Cada fragmento queda dentro de la pantalla, sin salto de línea automático.
                chunks = re.split(r'\x1b\[(\d+);(\d+)H', rendered)[1:]
                for y, x, text in zip(chunks[::3], chunks[1::3], chunks[2::3]):
                    self.assertLessEqual(int(y), rows)
                    self.assertLessEqual(int(x)+m.text_width(text)-1, cols)
                targets = [hit for hit in app.hits if hit[3][0] == 'target']
                self.assertEqual(len(targets), 20)
                x, y, _, _ = targets[-1]
                app.act(f'\x1b[<0;{x};{y}M')
                self.assertEqual(app.target, 19)
                x, y, width, _ = next(hit for hit in app.hits if hit[3] == ('channel', 0))
                app.act(f'\x1b[<0;{x};{y}M')
                self.assertEqual(app.colors[19][0], 0)
                app.act(f'\x1b[<32;{x+width-1};{y}M')
                self.assertEqual(app.colors[19][0], 255)
                with patch('sys.stdout', new_callable=io.StringIO) as output:
                    app.draw()
                self.assertIn(m.sgr(app.colors[19])+'capabilities*', output.getvalue())
                app.act('c')
                with patch('sys.stdout', new_callable=io.StringIO) as output:
                    app.draw()
                self.assertIn('Dracula', output.getvalue())
                self.assertIn('Nord', output.getvalue())
                app.act('\x1b')
        with patch.object(m.shutil, 'get_terminal_size', return_value=(60, 20)), patch('sys.stdout', new_callable=io.StringIO):
            app.draw()
        self.assertEqual(app.hits, [])

    def test_preset_hover_previews_without_changing_edited_colors(self):
        path = Path.home()/'.bashrc'
        path.write_text('# demo\n')
        app = m.App(path)
        app.colors[0] = [12, 34, 56]
        edited = copy.deepcopy(app.colors)
        saved = copy.deepcopy(app.saved)

        def draw():
            with patch.object(m.shutil, 'get_terminal_size', return_value=(100, 32)), patch('sys.stdout', new_callable=io.StringIO) as output:
                app.draw()
            return output.getvalue()

        app.act('c')
        self.assertIn(m.ESC+'?1003h', draw())
        x, y, _, _ = next(hit for hit in app.hits if hit[3] == ('preset', 1))
        app.act(f'\x1b[<35;{x};{y}M')
        self.assertEqual(app.preset_index, 1)
        rendered = draw()
        self.assertIn('Probar: Dracula', rendered)
        self.assertIn(m.sgr(app.presets['Dracula'][4])+'archivo.txt', rendered)
        self.assertEqual(app.colors, edited)
        self.assertEqual(app.saved, saved)
        app.act('\x1b[B')
        self.assertIn('Probar: Nord', draw())
        app.act('\x1b[<65;4;6M')
        self.assertIn('Probar: Monokai', draw())
        app.act('\x1b')
        self.assertEqual(app.colors, edited)
        self.assertIn(m.ESC+'?1003l', draw())
        app.act('c')
        draw()
        app.act(f'\x1b[<35;{x};{y}M')
        app.act('\r')
        self.assertIsNone(app.mode)
        self.assertEqual(app.colors, app.presets['Dracula'])
        self.assertEqual(app.saved, saved)
        self.assertEqual(path.read_text(), '# demo\n')

    def test_hsv_toggle_keyboard_and_achromatic_colors(self):
        path = Path.home()/'.bashrc'
        path.write_text('# demo\n')
        app = m.App(path)
        original = copy.deepcopy(app.colors)
        for _ in range(4):
            app.act('m')
            app.controls()
        self.assertEqual(app.colors, original)
        app.act('M')
        self.assertEqual(app.color_mode, 'HSV')
        # Elegir tono y saturación desde negro no debe perder estos ajustes.
        for _ in range(12): app.act('+')
        app.act('\t')
        app.act('\x1b[F')
        self.assertEqual(app.colors[0], [0, 0, 0])
        app.act('\t')
        app.act('\x1b[F')
        self.assertEqual(app.colors[0], [0, 255, 0])
        app.channel = 1
        app.act('\x1b[H')
        self.assertEqual(app.colors[0], [255, 255, 255])
        app.act('\x1b[F')
        self.assertEqual(app.colors[0], [0, 255, 0])
        app.act('m')
        self.assertEqual(app.controls()[1], [0, 255, 0])
        app.act('s')
        self.assertEqual(m.load_colors(path.read_text())[0], [0, 255, 0])

    def test_hsv_mouse_and_compact_rendering(self):
        path = Path.home()/'.bashrc'
        path.write_text('# demo\n')
        app = m.App(path)
        app.colors[0] = [255, 0, 0]
        app.act('m')
        with patch.object(m.shutil, 'get_terminal_size', return_value=(80, 32)), patch('sys.stdout', new_callable=io.StringIO) as output:
            app.draw()
        self.assertIn('EDITAR COLOR · HSV', output.getvalue())
        self.assertIn('100%', output.getvalue())
        x, y, width, _ = next(hit for hit in app.hits if hit[3] == ('channel', 0))
        app.act(f'\x1b[<0;{x+(width-1)//2};{y}M')
        self.assertTrue(160 <= app.controls()[1][0] <= 190)
        x, y, width, _ = next(hit for hit in app.hits if hit[3] == ('channel', 2))
        app.act(f'\x1b[<32;{x};{y}M')
        self.assertEqual(app.colors[0], [0, 0, 0])
        app.act(f'\x1b[<32;{x+width-1};{y}M')
        self.assertEqual(max(app.colors[0]), 255)
        app.act('r')
        self.assertEqual(app.controls()[1], [0, 0, 0])

    def test_saving_a_combination_always_opens_name_prompt(self):
        path = Path.home()/'.bashrc'
        path.write_text('# demo\n')
        app = m.App(path)
        with patch.object(m.shutil, 'get_terminal_size', return_value=(100, 32)), patch('sys.stdout', new_callable=io.StringIO) as output:
            app.draw()
            app.act('n')
            app.draw()
        self.assertEqual(app.mode, 'name')
        self.assertIn('Guardar combinación · Nombre:', output.getvalue())
        app.act('\x1b')
        app.act('g')
        self.assertEqual(app.mode, 'name')
        for key in 'Mi tema': app.act(key)
        app.act('\r')
        self.assertIn('Mi tema', m.load_presets(app.presets_path))

    def test_mouse_keyboard_and_save_in_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.bashrc'
            path.write_text('# demo\n')
            master, slave = pty.openpty()
            import fcntl, struct, termios
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 32,100,0,0))
            proc = subprocess.Popen([str(ROOT/'colorssh'), '--bashrc', str(path), '--presets', str(Path(directory)/'presets.json')], stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            output = bytearray()
            def wait_for(needle):
                deadline = time.monotonic()+5
                while needle not in output and time.monotonic()<deadline:
                    if select.select([master], [], [], .1)[0]:
                        try: output.extend(os.read(master, 65536))
                        except OSError: break
                self.assertIn(needle, output)
            try:
                wait_for(b'COLORSSH')
                os.write(master, b'\x1b[<0;89;5M')
                wait_for(b'#ff0000')
                os.write(master, b'\t\x1b[C' + b's')
                wait_for(b'Guardado.')
                os.write(master, 'nTema español\r'.encode())
                wait_for('Combinación guardada: Tema español'.encode())
                self.assertIn('Tema español', m.load_presets(Path(directory)/'presets.json'))
                os.write(master, b'q')
                proc.wait(timeout=5)
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(m.load_colors(path.read_text())[0], [255,1,0])
                self.assertEqual(len(list(m.config_dir().glob('.bashrc.bak.*'))), 1)
                self.assertEqual(list(Path(directory).glob('.bashrc.bak.*')), [])
            finally:
                if proc.poll() is None: proc.kill(); proc.wait()
                os.close(master)


if __name__ == '__main__': unittest.main()
