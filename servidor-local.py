#!/usr/bin/env python3
import gi
import subprocess
import os
import threading
import glob

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

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
        super().__init__(title=f"🐈 TETO PANEL - {distro}")
        self.set_wmclass("Teto Panel", "Teto Panel")
        self.set_border_width(15)
        self.set_default_size(400, 500)
        self.set_resizable(False)

        # --- Configuración Visual (Dark Mode & CSS) ---
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        css_provider = Gtk.CssProvider()
        css = b"""
        window { background-color: #212121; color: #eeeeee; }
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

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

       
        label_title = Gtk.Label()
        label_title.set_markup("<span foreground='#00FFFF' size='large' weight='bold'>==================================\n      TETO PANEL - DESARROLLO\n==================================</span>")
        vbox.pack_start(label_title, False, False, 0)

       
        self.status_label = Gtk.Label()
        vbox.pack_start(self.status_label, False, False, 5)
       
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, halign=Gtk.Align.CENTER)
        vbox.pack_start(grid, True, True, 0)

      
        buttons = [
            ("🚀 Iniciar Entorno", "#2e7d32", self.on_start_env, 0, 0),
            ("💤 Apagar Todo", "#c62828", self.on_stop_env, 0, 1),
            ("🐘 Cambiar PHP", "#f9a825", self.on_change_php, 1, 0),
            ("🌐 Nuevo VHost", "#ad1457", self.on_create_vhost, 1, 1),
            ("📧 Abrir Mailpit", "#1565c0", self.on_open_mailpit, 2, 0),
            ("📂 Directorio WWW", "#6a1b9a", self.on_open_www, 2, 1),
            ("🧹 Optimizar RAM", "#ef6c00", self.on_optimize_ram, 3, 0),
            ("🔐 Clave DB", "#00838f", self.on_change_db_pass, 3, 1),
            ("🔌 Probar DB", "#455a64", self.on_check_db_conn, 4, 0),
            ("📜 Ver Logs", "#546e7a", self.on_view_logs, 4, 1),
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

       
        exit_btn = Gtk.Button(label="🚪 Salir y Limpiar")
        exit_btn.connect("clicked", Gtk.main_quit)
        vbox.pack_end(exit_btn, False, False, 5)

      
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
            subprocess.run(["pkexec", "systemctl", "start", "apache2", "mariadb"])
            subprocess.Popen(["mailpit"], stdout=subprocess.DEVNULL)
            subprocess.Popen(["code", "/var/www/html/"])
            subprocess.Popen(["xdg-open", "http://localhost"])
            
            nav_path = os.path.expanduser("~/AppImages/navicat_premium_lite_17.appimage")
            if subprocess.run(["pgrep", "-f", "navicat"], stdout=subprocess.DEVNULL).returncode != 0:
                if os.path.exists(nav_path):
                    subprocess.Popen([nav_path], stdout=subprocess.DEVNULL)
        threading.Thread(target=task, daemon=True).start()

    def on_stop_env(self, btn):
        def task():
            subprocess.run(["pkexec", "systemctl", "stop", "apache2", "mariadb"])
            subprocess.run(["pkill", "mailpit"])
            subprocess.run(["pkill", "code"])
        threading.Thread(target=task, daemon=True).start()

    def on_open_www(self, btn):
        subprocess.Popen(["nautilus", "/var/www/html/"])

    def on_optimize_ram(self, btn):
        def task():
            
            subprocess.run(["pkexec", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"])
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
                
                subprocess.run(["pkexec", "sh", "-c", cmd])
                GLib.idle_add(self.update_status)
                GLib.idle_add(self.show_message, "PHP Cambiado", f"El sistema ahora usa {selected}")
            
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
                # Configuración base HTTP (Puerto 80)
                conf = (f"<VirtualHost *:80>\n"
                        f"    ServerName {domain}\n"
                        f"    DocumentRoot /var/www/html/{folder}\n"
                        f"    <Directory /var/www/html/{folder}>\n"
                        f"        AllowOverride All\n"
                        f"        Require all granted\n"
                        f"    </Directory>\n"
                        f"</VirtualHost>")

                cmd_ssl = ""
                if use_ssl:
                    # Añadir configuración HTTPS (Puerto 443)
                    conf += (f"\n<VirtualHost *:443>\n"
                             f"    ServerName {domain}\n"
                             f"    DocumentRoot /var/www/html/{folder}\n"
                             f"    SSLEngine on\n"
                             f"    SSLCertificateFile /etc/ssl/certs/{domain}.crt\n"
                             f"    SSLCertificateKeyFile /etc/ssl/private/{domain}.key\n"
                             f"    <Directory /var/www/html/{folder}>\n"
                             f"        AllowOverride All\n"
                             f"        Require all granted\n"
                             f"    </Directory>\n"
                             f"</VirtualHost>")
                    
                    # Comando para generar certificados y activar módulo SSL
                    cmd_ssl = (f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
                               f"-keyout /etc/ssl/private/{domain}.key "
                               f"-out /etc/ssl/certs/{domain}.crt "
                               f"-subj '/C=US/ST=Dev/L=Local/O=TetoPanel/CN={domain}'; "
                               f"a2enmod ssl; ")

                tmp_file = f"/tmp/{domain}.conf"
                with open(tmp_file, "w") as f: f.write(conf)
                
            
                cmd = (f"{cmd_ssl}"
                       f"mv {tmp_file} /etc/apache2/sites-available/{domain}.conf; "
                       f"mkdir -p /var/www/html/{folder}; a2ensite {domain}.conf; "
                       f"grep -q '{domain}' /etc/hosts || echo '127.0.0.1 {domain}' >> /etc/hosts; "
                       f"systemctl reload apache2")
                
                subprocess.run(["pkexec", "sh", "-c", cmd])
                GLib.idle_add(self.show_message, "Éxito", f"Host {domain} creado {'con SSL ' if use_ssl else ''}y activado.")
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
                subprocess.run(["pkexec", "sh", "-c", cmd])
                GLib.idle_add(self.show_message, "Éxito", "Clave de base de datos actualizada.")
            threading.Thread(target=task, daemon=True).start()
        else:
            dialog.destroy()

    def on_check_db_conn(self, btn):
        def task():
           
            res = subprocess.run(["pkexec", "mysqladmin", "ping"], capture_output=True, text=True)
            if res.returncode == 0:
                GLib.idle_add(self.show_message, "Conexión Exitosa", f"MariaDB está operativa y respondiendo:\n{res.stdout.strip()}")
            else:
                GLib.idle_add(self.show_message, "Sin Conexión", f"No se pudo conectar a la base de datos.\nError: {res.stderr.strip()}")
        threading.Thread(target=task, daemon=True).start()

    def on_view_logs(self, btn):
        dialog = Gtk.Dialog(title="Logs de Apache (Error)", transient_for=self, flags=0)
        dialog.set_default_size(700, 400)
        
        box = dialog.get_content_area()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_border_width(10)
        box.add(scrolled)
        
        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_monospace(True)
        scrolled.add(textview)
        
        def update_view(text):
            buf = textview.get_buffer()
            buf.set_text(text)
            mark = buf.create_mark("end", buf.get_end_iter(), False)
            textview.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)

        def task():
            cmd = ["pkexec", "tail", "-n", "50", "/var/log/apache2/error.log"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            GLib.idle_add(update_view, res.stdout if res.returncode == 0 else f"Error: {res.stderr}")

        btn_refresh = dialog.add_button("🔄 Actualizar", 1)
        btn_refresh.connect("clicked", lambda x: threading.Thread(target=task, daemon=True).start())
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        
        dialog.show_all()
        threading.Thread(target=task, daemon=True).start()
        dialog.run()
        dialog.destroy()

if __name__ == "__main__":
    win = TetoPanel()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()