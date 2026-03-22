#!/usr/bin/env python3
import gi
import subprocess
import os
import threading
import glob
import json
import socket
import sys

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf
try:
    gi.require_version("Vte", "2.91")
    from gi.repository import Vte
except ValueError:
    Vte = None
try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
except (ValueError, ImportError):
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    except (ValueError, ImportError):
        AppIndicator3 = None

class TetoPanel(Gtk.Window):
    def __init__(self):
        distro = "Linux"
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=", 1)[1].strip().strip('"')
                        break
        except:
            pass

        GLib.set_prgname("teto-panel")
        super().__init__(title=f" TETO PANEL V-0.5 - {distro}")
        self.set_wmclass("Teto Panel", "Teto Panel")
        self.set_border_width(15)

        # Singleton / Instancia Única
        self.app_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # Intenta reservar el nombre del socket (Abstract Namespace)
            self.app_socket.bind('\0teto_panel_lock')
            self.app_socket.listen(1)
            
            def socket_listener():
                while True:
                    try:
                        conn, _ = self.app_socket.accept()
                        if conn.recv(1024) == b"SHOW":
                            GLib.idle_add(self.present)
                        conn.close()
                    except: break
            threading.Thread(target=socket_listener, daemon=True).start()
        except socket.error:
            # Ya existe, enviar señal para mostrarlo y salir
            try:
                c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                c.connect('\0teto_panel_lock')
                c.send(b"SHOW")
                c.close()
            except: pass
            sys.exit(0)

        # Configurar HeaderBar (Barra de título personalizada)
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = self.get_title()
        self.set_titlebar(header)

        btn_settings = Gtk.Button(label="⋮")
        btn_settings.set_tooltip_text("Configuración")
        btn_settings.connect("clicked", self.on_open_settings)
        header.pack_end(btn_settings)

        # Habilitar transparencia visual (canal alfa)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        self.teto_player = None
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        css_provider = Gtk.CssProvider()
        css = b"""
        window { background-color: rgba(33, 33, 33, 0.85); color: #eeeeee; }
        label { font-family: 'Ubuntu', 'Segoe UI', sans-serif; }
        button {
            border-radius: 12px;
            border: none;
            padding: 10px;
            margin: 4px;
            color: white;
            font-weight: bold;
            box-shadow: 0 3px 5px rgba(0,0,0,0.3);
            transition: all 200ms ease;
        }
        button:hover { opacity: 0.9; box-shadow: 0 5px 9px rgba(0,0,0,0.5); }
        button:active { opacity: 0.7; }
        """
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.set_default_size(900, 700)
        self.set_resizable(True)
        self.load_config()
        self.connect("delete-event", self.on_window_delete)

        # Configuración System Tray (Soporte AppIndicator + Legacy)
        self.tray_menu = self.create_tray_menu()
        
        if AppIndicator3:
            self.indicator = AppIndicator3.Indicator.new("teto-panel", "indicator-messages", AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.indicator.set_icon_full("/home/gato/si/icon.png", "Teto Panel")
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.indicator.set_menu(self.tray_menu)
        else:
            self.status_icon = Gtk.StatusIcon()
            self.status_icon.set_from_file("/home/gato/si/icon.png")
            self.status_icon.set_tooltip_text("Teto Panel")
            self.status_icon.connect("activate", self.on_tray_activate)
            self.status_icon.connect("popup-menu", self.on_tray_popup)

        self.sudo_pass = self.get_sudo_password()

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_vbox)

        paned = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        paned.set_margin_top(0)
        main_vbox.pack_start(paned, True, True, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        paned.pack_start(vbox, False, False, 0)

        try:
            logo_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale("/home/gato/si/logo.png", 280, -1, True)
            logo_ev = Gtk.EventBox()
            logo_ev.set_visible_window(False)
            logo_ev.add(Gtk.Image.new_from_pixbuf(logo_pb))
            logo_ev.connect("button-press-event", lambda w, e: subprocess.Popen(["xdg-open", "https://kasaneteto.jp/"]))
            logo_ev.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
            logo_ev.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
            vbox.pack_start(logo_ev, False, False, 5)
        except Exception:
            vbox.pack_start(Gtk.Label(label="TETO PANEL"), False, False, 0)

       
        self.status_label = Gtk.Label()
        vbox.pack_start(self.status_label, False, False, 5)
       
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, halign=Gtk.Align.CENTER)
        vbox.pack_start(grid, True, True, 0)

      
        buttons = [
            ("🚀 Iniciar Entorno", "#590591", self.on_start_env, 0, 0),
            ("💤 Apagar Todo", "#690808", self.on_stop_env, 0, 1),
            ("🐘 Cambiar PHP", "#590591", self.on_change_php, 1, 0),
            ("🌐 Nuevo VHost", "#690808", self.on_create_vhost, 1, 1),
            ("📧 Abrir Mailpit", "#590591", self.on_open_mailpit, 2, 0),
            ("📂 Directorio WWW", "#690808", self.on_open_www, 2, 1),
            ("🧹 Optimizar RAM", "#590691", self.on_optimize_ram, 3, 0),
            ("🔐 Clave DB", "#690808", self.on_change_db_pass, 3, 1),
            ("🔌 Probar DB", "#590591", self.on_check_db_conn, 4, 0),
            (" Terminal", "#690808", self.on_open_terminal, 4, 1),
        ]

        for text, color, func, row, col in buttons:
            btn = Gtk.Button(label=text)
            btn.connect("clicked", func)
            
           
            ctx = btn.get_style_context()
            p = Gtk.CssProvider()
            css_btn = f"button {{ background-color: {color}; background-image: none; }}".encode()
            p.load_from_data(css_btn)
            ctx.add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
            grid.attach(btn, col, row, 1, 1)

        try:
            teto_pb = GdkPixbuf.Pixbuf.new_from_file_at_scale("/home/gato/si/teto.png", 110, -1, True)
            teto_ev = Gtk.EventBox()
            teto_ev.set_visible_window(False)
            teto_ev.add(Gtk.Image.new_from_pixbuf(teto_pb))
            teto_ev.connect("button-press-event", self.on_play_teto)
            teto_ev.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
            teto_ev.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
            vbox.pack_end(teto_ev, False, False, 10)
        except Exception:
            pass

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        paned.pack_start(right_box, True, True, 0)
        
        self.projects_label = Gtk.Label(label=f"<b>📂 Proyectos ({self.project_dir})</b>", use_markup=True, xalign=0)
        right_box.pack_start(self.projects_label, False, False, 5)
        
        scrolled = Gtk.ScrolledWindow()
        right_box.pack_start(scrolled, True, True, 0)
        
        self.project_list = Gtk.ListBox()
        self.project_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(self.project_list)
        self.refresh_projects()

        term_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        term_box.set_size_request(-1, 80)
        main_vbox.pack_end(term_box, False, True, 0)
        
        if Vte:
            terminal = Vte.Terminal()
            env_list = [f"{k}={v}" for k, v in os.environ.items()] + [f"SUDO_PASS={self.sudo_pass}"]
            terminal.spawn_async(
                Vte.PtyFlags.DEFAULT, os.environ['HOME'], 
                ["/bin/bash", "-c", "echo '--- 📜 Apache Error Log ---'; echo $SUDO_PASS | sudo -S tail -f /var/log/apache2/error.log; exec bash"], env_list, 
                GLib.SpawnFlags.DO_NOT_REAP_CHILD, None, None, -1, None, None
            )
            terminal.connect("button-press-event", self.on_term_click)
            term_box.pack_start(terminal, True, True, 0)
        else:
            term_box.pack_start(Gtk.Label(label="Instala gir1.2-vte-2.91 para ver la terminal aquí."), True, True, 0)

      
        GLib.timeout_add_seconds(3, self.update_status)
        self.update_status()

    def update_status(self):
        
        def check_service(name):
            res = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
            return "🟢" if res.stdout.strip() == "active" else "🔴"

        php_v = subprocess.check_output("php -v | head -n 1 | cut -d ' ' -f 2", shell=True, text=True).strip()
        
        status_text = (f"🌐 Apache: {check_service('apache2')} | "
                       f"🐬 MariaDB: {check_service('mariadb')}\n"
                       f"🐘 PHP: {php_v}")
        self.status_label.set_markup(f"<b>{status_text}</b>")
        return True

    def refresh_projects(self):
        for child in self.project_list.get_children():
            self.project_list.remove(child)
        
        base = self.project_dir
        if os.path.exists(base):
            for item in sorted(os.listdir(base)):
                path = os.path.join(base, item)
                if os.path.isdir(path):
                    row = Gtk.ListBoxRow()
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                    row.add(box)
                    
                    box.pack_start(Gtk.Label(label=item, xalign=0), True, True, 5)
                    
                    btn_web = Gtk.Button(label="🌐")
                    btn_web.connect("clicked", lambda x, n=item: subprocess.Popen(["xdg-open", f"http://localhost/{n}"]))
                    box.pack_start(btn_web, False, False, 0)
                    
                    self.project_list.add(row)
        self.project_list.show_all()

    def load_config(self):
        self.config_path = os.path.expanduser("~/.teto-panel-config.json")
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                    self.project_dir = data.get("project_dir", "/var/www/html")
                    w, h = data.get("width", 900), data.get("height", 700)
                    self.resize(w, h)
                    if "x" in data and "y" in data:
                        self.move(data["x"], data["y"])
            else:
                self.project_dir = "/var/www/html"
                self.set_position(Gtk.WindowPosition.CENTER)
        except Exception:
            self.project_dir = "/var/www/html"

    def save_config(self, widget, event):
        try:
            size = self.get_size()
            pos = self.get_position()
            data = {"width": size.width, "height": size.height, "x": pos.root_x, "y": pos.root_y}
            with open(self.config_path, "w") as f:
                data["project_dir"] = self.project_dir
                json.dump(data, f)
        except Exception:
            pass
        return False

    def on_window_delete(self, widget, event):
        self.save_config(widget, event)
        self.hide()
        return True

    def create_tray_menu(self):
        menu = Gtk.Menu()
        item_show = Gtk.MenuItem(label="Mostrar/Ocultar Panel")
        item_show.connect("activate", lambda x: self.on_tray_activate(None))
        menu.append(item_show)
        menu.append(Gtk.SeparatorMenuItem())
        for name, func in [("🚀 Iniciar Servicios", self.on_start_env), ("💤 Detener Servicios", self.on_stop_env), ("📂 Abrir Proyectos", self.on_open_www)]:
            item = Gtk.MenuItem(label=name)
            item.connect("activate", func)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        item_quit = Gtk.MenuItem(label="❌ Cerrar Teto Panel")
        item_quit.connect("activate", lambda x: Gtk.main_quit())
        menu.append(item_quit)
        menu.show_all()
        return menu

    def on_tray_activate(self, icon):
        if self.is_visible():
            self.hide()
        else:
            self.present()

    def on_tray_popup(self, icon, button, time):
        self.tray_menu.popup(None, None, None, None, button, time)

    def get_sudo_password(self):
        dialog = Gtk.Dialog(title="🔑 Teto Auth", transient_for=self, flags=Gtk.DialogFlags.MODAL)
        dialog.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Desbloquear", Gtk.ResponseType.OK)
        dialog.set_default_size(350, 150)
        
        box = dialog.get_content_area()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        hbox.set_margin_top(15); hbox.set_margin_bottom(15); hbox.set_margin_start(15); hbox.set_margin_end(15)
        box.add(hbox)

        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale("/home/gato/si/teto.png", 80, -1, True)
            hbox.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
        except:
            hbox.pack_start(Gtk.Label(label="🔒"), False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        hbox.pack_start(vbox, True, True, 0)
        
        vbox.pack_start(Gtk.Label(label="<b>Contraseña de Administrador</b>", use_markup=True, xalign=0), False, False, 0)
        vbox.pack_start(Gtk.Label(label="Necesaria para gestionar servicios.", xalign=0), False, False, 0)

        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_activates_default(True)
        vbox.pack_start(entry, False, False, 5)
        
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        
        response = dialog.run()
        pwd = entry.get_text()
        dialog.destroy()
        return pwd if response == Gtk.ResponseType.OK else ""

    def run_sudo(self, cmd, **kwargs):
        kwargs["input"] = self.sudo_pass + "\n"
        kwargs["text"] = True
        return subprocess.run(["sudo", "-S"] + cmd, **kwargs)

    def show_message(self, title, text):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        dialog.format_secondary_text(text)
        dialog.run()
        dialog.destroy()

  
    def on_start_env(self, btn):
        def task():
            self.run_sudo(["systemctl", "start", "apache2", "mariadb"])
            
            if subprocess.run(["pgrep", "mailpit"], stdout=subprocess.DEVNULL).returncode != 0:
                subprocess.Popen(["mailpit"], stdout=subprocess.DEVNULL)
            
            if subprocess.run(["pgrep", "code"], stdout=subprocess.DEVNULL).returncode != 0:
                subprocess.Popen(["code", self.project_dir])
            
            subprocess.Popen(["xdg-open", "http://localhost"])
            
            nav_path = os.path.expanduser("~/AppImages/navicat_premium_lite_17.appimage")
            if subprocess.run(["pgrep", "-f", "navicat"], stdout=subprocess.DEVNULL).returncode != 0:
                if os.path.exists(nav_path):
                    subprocess.Popen([nav_path], stdout=subprocess.DEVNULL)
        threading.Thread(target=task, daemon=True).start()

    def on_stop_env(self, btn):
        self.hide()
        def task():
            self.run_sudo(["systemctl", "stop", "apache2", "mariadb"])
            subprocess.run(["pkill", "mailpit"])
            subprocess.run(["pkill", "code"])
            GLib.idle_add(Gtk.main_quit)
        threading.Thread(target=task, daemon=True).start()

    def on_open_www(self, btn):
        subprocess.Popen(["xdg-open", self.project_dir])

    def on_optimize_ram(self, btn):
        def task():
            
            self.run_sudo(["sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"])
        threading.Thread(target=task, daemon=True).start()

    def on_open_mailpit(self, btn):
        subprocess.Popen(["xdg-open", "http://localhost:8025"])

    def on_change_php(self, btn):
        
        versions = sorted(glob.glob("/usr/bin/php[0-9].[0-9]"))
        if not versions:
            self.show_message("Error", "No se encontraron versiones de PHP en /usr/bin/")
            return

        dialog = Gtk.Dialog(title="Cambiar Versión PHP", transient_for=self, flags=0)
        dialog.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Aplicar", Gtk.ResponseType.OK)
        dialog.set_default_size(300, 120)
        
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_border_width(20)
        
        box.add(Gtk.Label(label="Selecciona la versión a utilizar (CLI y Apache):"))
        
        combo = Gtk.ComboBoxText()
        for v in versions:
            combo.append_text(os.path.basename(v))
        combo.set_active(0)
        box.add(combo)
        
        dialog.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            selected = combo.get_active_text()
            dialog.destroy()
            
            def task():
                cmd = (f"for mod in /etc/apache2/mods-enabled/php*.load; do a2dismod $(basename $mod .load); done; "
                       f"a2enmod {selected}; "
                       f"update-alternatives --set php /usr/bin/{selected}; "
                       f"systemctl restart apache2")
                
                self.run_sudo(["sh", "-c", cmd])
                GLib.idle_add(self.update_status)
                GLib.idle_add(self.show_message, "PHP Cambiado", f"El sistema ahora usa {selected}")
            
            threading.Thread(target=task, daemon=True).start()
        else:
            dialog.destroy()

    def on_open_settings(self, btn):
        dialog = Gtk.Dialog(title="Configuración Teto Panel", transient_for=self, flags=0)
        dialog.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Guardar y Aplicar", Gtk.ResponseType.OK)
        dialog.set_default_size(400, 150)
        
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_border_width(20)
        
        box.add(Gtk.Label(label="Carpeta raíz de proyectos (localhost):", xalign=0))
        
        chooser = Gtk.FileChooserButton(title="Seleccionar Carpeta", action=Gtk.FileChooserAction.SELECT_FOLDER)
        chooser.set_current_folder(self.project_dir)
        box.add(chooser)
        
        box.add(Gtk.Label(label="⚠️ Al cambiar esto, Apache se reconfigurará.", xalign=0))
        
        dialog.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            new_dir = chooser.get_filename()
            dialog.destroy()
            
            if new_dir and new_dir != self.project_dir:
                critical_paths = [os.path.expanduser("~"), "/", "/etc", "/usr", "/var", "/bin", "/sbin", "/lib", "/root", "/boot", "/opt"]
                if new_dir in critical_paths:
                    warn = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.WARNING,
                                             buttons=Gtk.ButtonsType.YES_NO, text="⚠️ ¡Advertencia de Seguridad!")
                    warn.format_secondary_text(f"Has seleccionado una carpeta crítica del sistema:\n'{new_dir}'\n\n"
                                               "Esto expondrá TODOS los archivos de esta ubicación al servidor web y modificará sus permisos de lectura/escritura.\n\n"
                                               "¿Estás completamente seguro de continuar?")
                    res = warn.run()
                    warn.destroy()
                    if res != Gtk.ResponseType.YES:
                        return

                self.project_dir = new_dir
                self.projects_label.set_markup(f"<b>📂 Proyectos ({self.project_dir})</b>")
                self.save_config(None, None)
                self.refresh_projects()
                
                def task():
                    # Configurar 000-default para apuntar a la nueva carpeta
                    # y dar permisos de directorio en apache2.conf (o vía conf independiente)
                    conf_content = (f"<VirtualHost *:80>\n"
                                    f"    ServerAdmin webmaster@localhost\n"
                                    f"    DocumentRoot {self.project_dir}\n"
                                    f"    <Directory {self.project_dir}>\n"
                                    f"        Options Indexes FollowSymLinks\n"
                                    f"        AllowOverride All\n"
                                    f"        Require all granted\n"
                                    f"    </Directory>\n"
                                    f"    ErrorLog ${{APACHE_LOG_DIR}}/error.log\n"
                                    f"    CustomLog ${{APACHE_LOG_DIR}}/access.log combined\n"
                                    f"</VirtualHost>")
                    
                    tmp_file = "/tmp/000-default.conf"
                    with open(tmp_file, "w") as f: f.write(conf_content)
                    
                    home = os.path.expanduser("~")
                    cmd_home_perm = ""
                    if self.project_dir.startswith(home):
                        cmd_home_perm = f"chmod +x '{home}'; "

                    cmd = (f"mv {tmp_file} /etc/apache2/sites-available/000-default.conf; "
                           f"chown $SUDO_USER:$SUDO_USER '{self.project_dir}'; "
                           f"chmod 755 '{self.project_dir}'; "
                           f"{cmd_home_perm}"
                           f"systemctl restart apache2")
                    self.run_sudo(["sh", "-c", cmd])
                    GLib.idle_add(self.show_message, "Configuración Actualizada", f"Localhost ahora apunta a:\n{self.project_dir}")
                threading.Thread(target=task, daemon=True).start()
        else:
            dialog.destroy()

    def on_create_vhost(self, btn):
        dialog = Gtk.Dialog(title="Nuevo Virtual Host", transient_for=self, flags=0)
        dialog.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Crear", Gtk.ResponseType.OK)
        dialog.set_default_size(350, 220)
        
        grid = Gtk.Grid(column_spacing=10, row_spacing=15, margin=20)
        
        entry_domain = Gtk.Entry()
        entry_domain.set_placeholder_text("ejemplo.test")
        entry_dir = Gtk.Entry()
        entry_dir.set_placeholder_text("nombre-carpeta")
        check_ssl = Gtk.CheckButton(label="Habilitar SSL (https://)")
        
        grid.attach(Gtk.Label(label="Dominio:", xalign=0), 0, 0, 1, 1)
        grid.attach(entry_domain, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="Carpeta en WWW:", xalign=0), 0, 1, 1, 1)
        grid.attach(entry_dir, 1, 1, 1, 1)
        grid.attach(check_ssl, 1, 2, 1, 1)
        
        dialog.get_content_area().add(grid)
        dialog.show_all()
        
        if dialog.run() == Gtk.ResponseType.OK:
            domain = entry_domain.get_text().strip()
            folder = entry_dir.get_text().strip()
            use_ssl = check_ssl.get_active()
            dialog.destroy()
            
            if not domain or not folder:
                self.show_message("Error", "Debes completar ambos campos.")
                return

            def task():
                conf = (f"<VirtualHost *:80>\n"
                        f"    ServerName {domain}\n"
                        f"    DocumentRoot {self.project_dir}/{folder}\n"
                        f"    <Directory {self.project_dir}/{folder}>\n"
                        f"        AllowOverride All\n"
                        f"        Require all granted\n"
                        f"    </Directory>\n"
                        f"</VirtualHost>")

                cmd_ssl = ""
                if use_ssl:
                    conf += (f"\n<VirtualHost *:443>\n"
                             f"    ServerName {domain}\n"
                             f"    DocumentRoot {self.project_dir}/{folder}\n"
                             f"    SSLEngine on\n"
                             f"    SSLCertificateFile /etc/ssl/certs/{domain}.crt\n"
                             f"    SSLCertificateKeyFile /etc/ssl/private/{domain}.key\n"
                             f"    <Directory {self.project_dir}/{folder}>\n"
                             f"        AllowOverride All\n"
                             f"        Require all granted\n"
                             f"    </Directory>\n"
                             f"</VirtualHost>")
                    
                    cmd_ssl = (f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
                               f"-keyout /etc/ssl/private/{domain}.key "
                               f"-out /etc/ssl/certs/{domain}.crt "
                               f"-subj '/C=US/ST=Dev/L=Local/O=TetoPanel/CN={domain}'; "
                               f"a2enmod ssl; ")

                tmp_file = f"/tmp/{domain}.conf"
                with open(tmp_file, "w") as f: f.write(conf)
                
            
                cmd = (f"{cmd_ssl}"
                       f"mv {tmp_file} /etc/apache2/sites-available/{domain}.conf; "
                       f"mkdir -p {self.project_dir}/{folder}; "
                       f"chown -R $SUDO_USER:$SUDO_USER {self.project_dir}/{folder}; "
                       f"chmod -R 775 {self.project_dir}/{folder}; "
                       f"a2ensite {domain}.conf; "
                       f"grep -q '{domain}' /etc/hosts || echo '127.0.0.1 {domain}' >> /etc/hosts; "
                       f"systemctl reload apache2")
                
                self.run_sudo(["sh", "-c", cmd])
                GLib.idle_add(self.show_message, "Éxito", f"Host {domain} creado {'con SSL ' if use_ssl else ''}y activado.")
                GLib.idle_add(self.refresh_projects)
            threading.Thread(target=task, daemon=True).start()
        else:
            dialog.destroy()

    def on_change_db_pass(self, btn):
        dialog = Gtk.Dialog(title="Cambiar Clave MariaDB", transient_for=self, flags=0)
        dialog.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Cambiar", Gtk.ResponseType.OK)
        dialog.set_default_size(300, 150)
        
        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_border_width(20)
        
        box.add(Gtk.Label(label="Nueva contraseña para root@localhost:"))
        
        entry_pass = Gtk.Entry()
        entry_pass.set_visibility(False)  
        box.add(entry_pass)
        
        dialog.show_all()
        
        if dialog.run() == Gtk.ResponseType.OK:
            new_pass = entry_pass.get_text()
            dialog.destroy()
            def task():
              
                safe_pass = new_pass.replace("'", "\\'")
                cmd = f"mysql -e \"ALTER USER 'root'@'localhost' IDENTIFIED BY '{safe_pass}'; FLUSH PRIVILEGES;\""
                self.run_sudo(["sh", "-c", cmd])
                GLib.idle_add(self.show_message, "Éxito", "Clave de base de datos actualizada.")
            threading.Thread(target=task, daemon=True).start()
        else:
            dialog.destroy()

    def on_check_db_conn(self, btn):
        def task():
           
            res = self.run_sudo(["mysqladmin", "ping"], capture_output=True)
            if res.returncode == 0:
                GLib.idle_add(self.show_message, "Conexión Exitosa", f"MariaDB está operativa y respondiendo:\n{res.stdout.strip()}")
            else:
                GLib.idle_add(self.show_message, "Sin Conexión", f"No se pudo conectar a la base de datos.\nError: {res.stderr.strip()}")
        threading.Thread(target=task, daemon=True).start()

    def on_term_click(self, widget, event):
        if event.button == 3:
            menu = Gtk.Menu()
            item = Gtk.MenuItem(label="Copiar")
            item.connect("activate", lambda x: widget.copy_clipboard_format(Vte.Format.TEXT))
            menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, None, event.button, event.time)
            return True
        return False

    def on_open_terminal(self, btn):
        try:
            subprocess.Popen(["x-terminal-emulator"], cwd=self.project_dir)
        except FileNotFoundError:
            self.show_message("Error", "No se encontró un emulador de terminal (x-terminal-emulator).")

    def on_play_teto(self, widget, event):
        if self.teto_player and self.teto_player.poll() is None:
            return

        mp3 = "/home/gato/si/teto.mp3"
        if not os.path.exists(mp3): return
        
        # Intentar reproductores ligeros sin interfaz
        for cmd in [["ffplay", "-nodisp", "-autoexit"], ["mpv", "--no-video"], ["mpg123"], ["cvlc", "--play-and-exit", "--no-video"]]:
            try:
                self.teto_player = subprocess.Popen(cmd + [mp3], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError: continue

if __name__ == "__main__":
    win = TetoPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()