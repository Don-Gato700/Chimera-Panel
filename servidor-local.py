#!/usr/bin/env python3
import gi
import subprocess
import os
import threading
import glob
import json
import socket
import sys
import shutil
import pwd

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

class PanelTeto(Gtk.Window):
    # Inicializo la ventana y configuro todo, pero usando funciones separadas porsiaca
    def __init__(self):
        self.ruta_base = os.path.dirname(os.path.abspath(__file__))
        self._detectar_distro()
        GLib.idle_add(self._verificar_dependencias)
        self._configurar_propiedades_ventana()
        self._asegurar_instancia_unica()
        self._configurar_cabecera()
        self._aplicar_estilos()
        self.cargar_configuracion()
        
        self.connect("delete-event", self.al_cerrar_ventana)
        self.connect("key-press-event", self.al_pulsar_tecla)

        self.menu_bandeja = self.crear_menu_bandeja()
        self._configurar_bandeja()

        self.autenticar_sudo()

        self._construir_layout_principal()
        
        # Arranco el monitor de estado
        GLib.timeout_add_seconds(3, self.actualizar_estado)
        self.actualizar_estado()
        
        # Verifico actualizaciones en segundo plano al arrancar (5s delay)
        GLib.timeout_add_seconds(5, lambda: self._lanzar_hilo(self._verificar_actualizaciones_bg) or False)

    # --- MÉTODOS DE CONFIGURACIÓN E INTERFAZ ---

    # Averiguo en qué Linux estoy
    def _detectar_distro(self):
        self.distribucion = "Linux"
        try:
            with open("/etc/os-release") as f:
                for linea in f:
                    if linea.startswith("PRETTY_NAME="):
                        self.distribucion = linea.split("=", 1)[1].strip().strip('"')
                        break
        except: pass

    # Configuro título, tamaño y bordes
    def _configurar_propiedades_ventana(self):
        GLib.set_prgname("teto-panel")
        super().__init__(title=f" TETO PANEL V-0.8 - {self.distribucion}")
        self.set_wmclass("Teto Panel", "Teto Panel")
        self.set_border_width(15)
        self.set_default_size(900, 700)
        self.set_resizable(True)
        self.reproductor_teto = None
        self.proc_tail = None
        
        pantalla = self.get_screen()
        visual = pantalla.get_rgba_visual()
        if visual and pantalla.is_composited():
            self.set_visual(visual)

    # Evito que se abra la app dos veces usando un socket
    def _asegurar_instancia_unica(self):
        self.socket_app = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.socket_app.bind('\0teto_panel_lock')
            self.socket_app.listen(1)
            self._lanzar_hilo(self._escuchar_socket)
        except socket.error:
            self._notificar_instancia_existente()
            sys.exit(0)

    def _escuchar_socket(self):
        while True:
            try:
                conexion, _ = self.socket_app.accept()
                if conexion.recv(1024) == b"SHOW":
                    GLib.idle_add(self.present)
                conexion.close()
            except: break

    def _notificar_instancia_existente(self):
        try:
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            c.connect('\0teto_panel_lock')
            c.send(b"SHOW")
            c.close()
        except: pass

    # Pongo la barra de título personalizada
    def _configurar_cabecera(self):
        cabecera = Gtk.HeaderBar()
        cabecera.set_show_close_button(True)
        cabecera.props.title = self.get_title()
        self.set_titlebar(cabecera)

        btn_ajustes = Gtk.Button(label="⋮")
        btn_ajustes.set_tooltip_text("Configuración")
        btn_ajustes.connect("clicked", self.al_abrir_ajustes)
        cabecera.pack_end(btn_ajustes)

    # Cargo el CSS oscuro y los estilos de botones
    def _aplicar_estilos(self):
        ajustes = Gtk.Settings.get_default()
        ajustes.set_property("gtk-application-prefer-dark-theme", True)

        estilo_css = b"""
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
        list { background-color: rgba(0, 0, 0, 0.2); border-radius: 8px; }
        row { background-color: transparent; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
        row:hover { background-color: rgba(255, 255, 255, 0.1); }
        """
        proveedor_css = Gtk.CssProvider()
        proveedor_css.load_from_data(estilo_css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), proveedor_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    # Configuro el icono de la bandeja del sistema
    def _configurar_bandeja(self):
        ruta_icono = os.path.join(self.ruta_base, "icon.png")
        if AppIndicator3:
            self.indicador = AppIndicator3.Indicator.new("teto-panel", "indicator-messages", AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.indicador.set_icon_full(ruta_icono, "Teto Panel")
            self.indicador.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.indicador.set_menu(self.menu_bandeja)
        else:
            self.icono_estado = Gtk.StatusIcon()
            self.icono_estado.set_from_file(ruta_icono)
            self.icono_estado.set_tooltip_text("Teto Panel")
            self.icono_estado.connect("activate", self.al_activar_bandeja)
            self.icono_estado.connect("popup-menu", self.al_popup_bandeja)

    # Construyo toda la estructura visual dentro de la ventana
    def _construir_layout_principal(self):
        caja_principal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(caja_principal)

        panel_dividido = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        panel_dividido.set_margin_top(0)
        caja_principal.pack_start(panel_dividido, True, True, 0)

        caja_izq = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        panel_dividido.pack_start(caja_izq, False, False, 0)

        self._agregar_logo(caja_izq)
        
        self.etiqueta_estado = Gtk.Label()
        caja_izq.pack_start(self.etiqueta_estado, False, False, 5)

        self._agregar_grid_botones(caja_izq)
        self._agregar_imagen_teto(caja_izq)

        self._construir_panel_derecho(panel_dividido)
        self._construir_terminal(caja_principal)

    def _agregar_logo(self, contenedor):
        try:
            pixbuf_logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(os.path.join(self.ruta_base, "logo.png"), 280, -1, True)
            evento_logo = Gtk.EventBox()
            evento_logo.set_visible_window(False)
            evento_logo.add(Gtk.Image.new_from_pixbuf(pixbuf_logo))
            evento_logo.connect("button-press-event", lambda w, e: subprocess.Popen(["xdg-open", "https://kasaneteto.jp/"]))
            evento_logo.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
            evento_logo.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
            contenedor.pack_start(evento_logo, False, False, 5)
        except Exception:
            contenedor.pack_start(Gtk.Label(label="TETO PANEL"), False, False, 0)

    def _agregar_grid_botones(self, contenedor):
        rejilla = Gtk.Grid(column_spacing=10, row_spacing=10, halign=Gtk.Align.CENTER)
        contenedor.pack_start(rejilla, True, True, 0)

        botones = [
            ("🚀 Iniciar Entorno", "#590591", self.al_iniciar_entorno, 0, 0),
            ("💤 Apagar Todo", "#690808", self.al_detener_entorno, 0, 1),
            ("🐘 Cambiar PHP", "#590591", self.al_cambiar_php, 1, 0),
            ("🌐 Nuevo VHost", "#690808", self.al_crear_vhost, 1, 1),
            ("📧 Abrir Mailpit", "#590591", self.al_abrir_mailpit, 2, 0),
            ("📊 Analizar Logs", "#690808", self.al_analizar_logs, 2, 1),
            ("🧹 Optimizar RAM", "#590691", self.al_optimizar_ram, 3, 0),
            ("🔐 Clave DB", "#690808", self.al_cambiar_clave_db, 3, 1),
            ("🔌 Probar DB", "#590591", self.al_probar_conexion_db, 4, 0),
            (" Terminal", "#690808", self.al_abrir_terminal_externa, 4, 1),
            ("🚑 Sanar Apache", "#590691", self.al_sanear_apache, 5, 0),
            ("🗑️ Borrar VHost", "#590808", self.al_borrar_vhost, 5, 1),
        ]

        for texto, color, funcion, fila, col in botones:
            btn = Gtk.Button(label=texto)
            btn.connect("clicked", funcion)
            # Le digo al botón que cambie el cursor a una mano cuando paso el ratón por encima para que se note
            btn.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
            btn.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
            # Estilo CSS por botón
            ctx = btn.get_style_context()
            p = Gtk.CssProvider()
            css_btn = f"button {{ background-color: {color}; background-image: none; }}".encode()
            p.load_from_data(css_btn)
            ctx.add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            rejilla.attach(btn, col, fila, 1, 1)

    def _agregar_imagen_teto(self, contenedor):
        try:
            pixbuf_teto = GdkPixbuf.Pixbuf.new_from_file_at_scale(os.path.join(self.ruta_base, "teto.png"), 110, -1, True)
            evento_teto = Gtk.EventBox()
            evento_teto.set_visible_window(False)
            evento_teto.add(Gtk.Image.new_from_pixbuf(pixbuf_teto))
            evento_teto.connect("button-press-event", self.al_reproducir_teto)
            evento_teto.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
            evento_teto.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
            contenedor.pack_end(evento_teto, False, False, 10)
        except Exception: pass

    def _construir_panel_derecho(self, contenedor):
        caja_derecha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        contenedor.pack_start(caja_derecha, True, True, 0)

        # Cabecera con título y botón de crear carpeta
        caja_cabecera = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caja_derecha.pack_start(caja_cabecera, False, False, 5)
        
        self.etiqueta_proyectos = Gtk.Label(label=f"<b>📂 Proyectos ({self.dir_proyectos})</b>", use_markup=True, xalign=0)
        caja_cabecera.pack_start(self.etiqueta_proyectos, True, True, 0)

        btn_nuevo = Gtk.Button(label="➕")
        btn_nuevo.set_tooltip_text("Crear nueva carpeta de proyecto")
        btn_nuevo.connect("clicked", self.al_crear_carpeta_proyecto)
        btn_nuevo.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
        btn_nuevo.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
        caja_cabecera.pack_start(btn_nuevo, False, False, 0)
        
        ventana_desplazable = Gtk.ScrolledWindow()
        caja_derecha.pack_start(ventana_desplazable, True, True, 0)
        
        self.lista_proyectos = Gtk.ListBox()
        self.lista_proyectos.set_selection_mode(Gtk.SelectionMode.NONE)
        ventana_desplazable.add(self.lista_proyectos)
        self.recargar_proyectos()
        
        # --- Sección de Monitorización (Debajo de la lista) ---
        caja_derecha.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 5)
        
        caja_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        caja_derecha.pack_start(caja_info, False, False, 5)
        
        self.lbl_puertos = Gtk.Label(xalign=0)
        self.lbl_puertos.set_markup("<small>Escaneando puertos...</small>")
        caja_info.pack_start(self.lbl_puertos, False, False, 0)
        
        caja_ram = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        caja_info.pack_start(caja_ram, False, False, 0)
        caja_ram.pack_start(Gtk.Label(label="RAM:", xalign=0), False, False, 0)
        
        self.bar_ram = Gtk.ProgressBar()
        self.bar_ram.set_show_text(True)
        caja_ram.pack_start(self.bar_ram, True, True, 0)

    def _construir_terminal(self, contenedor):
        caja_terminal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caja_terminal.set_size_request(-1, 80)
        contenedor.pack_end(caja_terminal, False, True, 0)
        
        if Vte:
            terminal = Vte.Terminal()
            terminal.set_input_enabled(False)
            terminal.connect("button-press-event", self.al_clic_terminal)
            caja_terminal.pack_start(terminal, True, True, 0)
            
            self._lanzar_hilo(self._leer_logs_apache, (terminal,))
        else:
            caja_terminal.pack_start(Gtk.Label(label="Instala gir1.2-vte-2.91 para ver la terminal aquí."), True, True, 0)

    def _leer_logs_apache(self, terminal):
        try:
            self.proc_tail = subprocess.Popen(
                ["sudo", "-n", "tail", "-f", "/var/log/apache2/error.log"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            terminal.feed(b"--- \xf0\x9f\x93\x9c Apache Error Log ---\r\n")
            while True:
                linea = self.proc_tail.stdout.readline()
                if not linea: break
                GLib.idle_add(terminal.feed, linea.encode("utf-8"))
        except Exception as e:
            GLib.idle_add(terminal.feed, f"\r\nError: {e}\r\n".encode("utf-8"))

    # --- LÓGICA DE LA APP ---

    def _verificar_dependencias(self):
        errores = []
        avisos = []
        paquetes_install = []

        # Librerías opcionales
        if Vte is None: avisos.append("gir1.2-vte-2.91 (Terminal integrada)")
        if AppIndicator3 is None: avisos.append("gir1.2-appindicator3-0.1 (Icono bandeja)")
        if Vte is None: 
            avisos.append("gir1.2-vte-2.91 (Terminal integrada)")
            paquetes_install.append("gir1.2-vte-2.91")
        if AppIndicator3 is None: 
            avisos.append("gir1.2-appindicator3-0.1 (Icono bandeja)")
            paquetes_install.append("gir1.2-appindicator3-0.1")

        # Binarios del sistema
        def check(cmd):
            return shutil.which(cmd) or any(os.path.exists(os.path.join(p, cmd)) for p in ["/usr/sbin", "/sbin"])

        if not check("apache2"): 
            errores.append("apache2 (Servidor Web)")
            paquetes_install.append("apache2")
            
        if not check("mariadbd") and not check("mysqld"): 
            errores.append("mariadb-server (Base de Datos)")
            paquetes_install.append("mariadb-server")
            
        if not check("mysql"): 
            errores.append("mariadb-client (Cliente DB)")
            paquetes_install.append("mariadb-client")
            
        if not check("php"): 
            errores.append("php (Stack Completo)")
            # Instalamos PHP y los módulos más comunes para desarrollo
            paquetes_install.extend(["php", "libapache2-mod-php", "php-mysql", "php-cli", "php-curl", "php-mbstring", "php-xml", "php-zip"])
            
        if not check("mailpit"): avisos.append("mailpit (Servidor de correo local)")

        if errores or avisos:
            msg = "El entorno no está completo:\n\n"
            if errores: msg += "⛔ CRÍTICO (Falta instalación):\n" + "\n".join(f"• {e}" for e in errores) + "\n\n"
            if avisos: msg += "⚠️ RECOMENDADO:\n" + "\n".join(f"• {a}" for a in avisos)
            
            self.mostrar_mensaje("Verificación de Sistema", msg)
            dialogo = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.NONE, text="Faltan Dependencias")
            dialogo.format_secondary_text(msg)
            dialogo.add_button("Ignorar", Gtk.ResponseType.CANCEL)
            
            if paquetes_install:
                btn = dialogo.add_button("🛠️ Instalar Automáticamente", Gtk.ResponseType.ACCEPT)
                btn.get_style_context().add_class("suggested-action")
            
            res = dialogo.run()
            dialogo.destroy()
            
            if res == Gtk.ResponseType.ACCEPT and paquetes_install:
                self._instalar_paquetes_sistema(paquetes_install)
        return False

    def _instalar_paquetes_sistema(self, paquetes):
        lista = " ".join(paquetes)
        # Comando para instalar en una terminal externa visible
        cmd = f"sudo apt update && sudo apt install -y {lista}; echo; echo '--- PROCESO TERMINADO ---'; echo 'Por favor reinicia el panel si instalaste librerías gráficas.'; read -p 'Presiona Enter para cerrar...'"
        try:
            subprocess.Popen(["x-terminal-emulator", "-e", "bash", "-c", cmd])
        except:
            self.mostrar_mensaje("Error", f"No se pudo abrir la terminal automática.\nEjecuta manualmente:\n\nsudo apt install {lista}")

    def _verificar_actualizaciones_bg(self):
        # Actualizo repositorios primero para ver lo último (silencioso)
        self.ejecutar_sudo(["apt", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        try:
            res = subprocess.run(["apt", "list", "--upgradable"], capture_output=True, text=True)
            if res.returncode != 0: return

            # Lista de software clave a vigilar
            claves = ["apache2", "mariadb-server", "mariadb-client", "mysql-server", "php"]
            pendientes = []
            
            for linea in res.stdout.splitlines():
                if "/" in linea:
                    nombre = linea.split("/")[0]
                    # Filtro si es uno de los clave o empieza por php/libapache
                    if nombre in claves or nombre.startswith("php") or nombre.startswith("libapache2"):
                        pendientes.append(nombre)
            
            if pendientes:
                lista_txt = "\n".join(f"• {p}" for p in pendientes[:5]) + ("\n..." if len(pendientes) > 5 else "")
                GLib.idle_add(self._preguntar_actualizar, lista_txt, pendientes)
        except: pass

    def _preguntar_actualizar(self, lista_txt, paquetes):
        dialogo = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.INFO, 
                                   buttons=Gtk.ButtonsType.YES_NO, text="Actualizaciones Disponibles")
        dialogo.format_secondary_text(f"Se han encontrado nuevas versiones para tus herramientas:\n\n{lista_txt}\n\n¿Quieres actualizarlas ahora?")
        res = dialogo.run()
        dialogo.destroy()
        
        if res == Gtk.ResponseType.YES:
            self._instalar_paquetes_sistema(paquetes)

    def al_pulsar_tecla(self, widget, evento):
        tecla = Gdk.keyval_name(evento.keyval)
        ctrl = (evento.state & Gdk.ModifierType.CONTROL_MASK)
        
        if ctrl and (tecla == "r" or tecla == "R"):
            self.recargar_proyectos()
            return True
        elif tecla == "F5":
            self.al_reiniciar_servicios(None)
            return True
        return False

    # Compruebo si Apache y MariaDB están activos para actualizar el texto
    def actualizar_estado(self):
        def verificar_servicio(nombre):
            res = subprocess.run(["systemctl", "is-active", nombre], capture_output=True, text=True)
            return "🟢" if res.stdout.strip() == "active" else "🔴"

        version_php = subprocess.check_output("php -v | head -n 1 | cut -d ' ' -f 2", shell=True, text=True).strip()
        
        texto_estado = (f"🌐 Apache: {verificar_servicio('apache2')} | "
                       f"🐬 MariaDB: {verificar_servicio('mariadb')}\n"
                       f"🐘 PHP: {version_php}")
        self.etiqueta_estado.set_markup(f"<b>{texto_estado}</b>")
        
        # Actualizo información de puertos (Verde = Escuchando)
        puertos = {"Apache": 80, "DB": 3306, "Mailpit": 8025}
        txt_p = []
        for nombre, puerto in puertos.items():
            color = "#e53935" # Rojo (Inactivo)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.05) # Timeout rápido para no congelar la UI
                if s.connect_ex(('127.0.0.1', puerto)) == 0:
                    color = "#43a047" # Verde (Activo)
                s.close()
            except: pass
            txt_p.append(f"{nombre}: <span foreground='{color}'><b>{puerto}</b></span>")
        self.lbl_puertos.set_markup(" | ".join(txt_p))
        
        # Actualizo monitor de RAM usando /proc/meminfo
        try:
            with open('/proc/meminfo', 'r') as f:
                d = {l.split(':')[0]: int(l.split(':')[1].split()[0]) for l in f if ':' in l}
            
            total = d.get('MemTotal', 1)
            # MemAvailable es más preciso que MemFree
            avail = d.get('MemAvailable', d.get('MemFree', 0))
            usado = total - avail
            self.bar_ram.set_fraction(usado / total)
            self.bar_ram.set_text(f"{int(usado/1024)}MB / {int(total/1024)}MB")
        except: pass
        
        return True

    # Busca las carpetas en el directorio web para listarlas
    def recargar_proyectos(self):
        for hijo in self.lista_proyectos.get_children():
            self.lista_proyectos.remove(hijo)
        
        base = self.dir_proyectos
        if os.path.exists(base):
            items = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
            items.sort(key=lambda x: (0 if x in self.favoritos else 1, x.lower()))
            
            for item in items:
                ruta = os.path.join(base, item)
                fila = Gtk.ListBoxRow()
                caja = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                fila.add(caja)
                
                es_fav = item in self.favoritos
                btn_fav = Gtk.Button(label="★" if es_fav else "☆")
                btn_fav.set_tooltip_text("Quitar de favoritos" if es_fav else "Fijar al principio")
                btn_fav.connect("clicked", self.al_alternar_favorito, item)
                
                ctx = btn_fav.get_style_context()
                p = Gtk.CssProvider()
                css_btn = f"button {{ background-image: none; background-color: transparent; box-shadow: none; font-size: 15px; color: {'#FFD700' if es_fav else '#666666'}; }} button:hover {{ color: #ffffff; }}".encode()
                p.load_from_data(css_btn)
                ctx.add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                
                caja.pack_start(btn_fav, False, False, 0)
                caja.pack_start(Gtk.Label(label=item, xalign=0), True, True, 5)
                
                # 1. Botón Basura (Primero)
                boton_borrar = Gtk.Button(label="🗑️")
                boton_borrar.set_tooltip_text("Eliminar proyecto (Carpeta)")
                boton_borrar.connect("clicked", self.al_borrar_proyecto, item)
                boton_borrar.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
                boton_borrar.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
                caja.pack_start(boton_borrar, False, False, 0)

                boton_carpeta = Gtk.Button(label="📂")
                boton_carpeta.set_tooltip_text("Abrir carpeta")
                boton_carpeta.connect("clicked", lambda x, n=item: subprocess.Popen(["xdg-open", os.path.join(base, n)]))
                boton_carpeta.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
                boton_carpeta.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
                caja.pack_start(boton_carpeta, False, False, 0)

                # 2. Botón Web (Luego)
                boton_web = Gtk.Button(label="🌐")
                boton_web.connect("clicked", lambda x, n=item: subprocess.Popen(["xdg-open", f"http://localhost/{n}"]))
                boton_web.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.HAND2)))
                boton_web.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None))
                caja.pack_start(boton_web, False, False, 0)
                
                self.lista_proyectos.add(fila)
        self.lista_proyectos.show_all()

    def al_alternar_favorito(self, btn, item):
        if item in self.favoritos:
            self.favoritos.remove(item)
        else:
            self.favoritos.append(item)
        self.guardar_configuracion(None, None)
        self.recargar_proyectos()

    def al_crear_carpeta_proyecto(self, btn):
        dialogo = Gtk.Dialog(title="Nuevo Proyecto", transient_for=self, flags=0)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Crear", Gtk.ResponseType.OK)
        dialogo.set_default_size(300, 100)
        
        caja = dialogo.get_content_area()
        caja.set_spacing(10); caja.set_border_width(20)
        caja.add(Gtk.Label(label="Nombre de la nueva carpeta:"))
        
        entrada = Gtk.Entry()
        caja.add(entrada)
        dialogo.show_all()
        
        if dialogo.run() == Gtk.ResponseType.OK:
            nombre = entrada.get_text().strip()
            dialogo.destroy()
            if nombre:
                self._lanzar_hilo(self._tarea_crear_carpeta_bg, (nombre,))
        else:
            dialogo.destroy()

    def _tarea_crear_carpeta_bg(self, nombre):
        ruta = os.path.join(self.dir_proyectos, nombre)
        try: usuario = pwd.getpwuid(os.getuid()).pw_name
        except: usuario = "www-data"
        
        # Creamos carpeta y asignamos permisos
        self.ejecutar_sudo(["mkdir", "-p", ruta])
        self.ejecutar_sudo(["chown", f"{usuario}:{usuario}", ruta])
        self.ejecutar_sudo(["chmod", "755", ruta])
        
        GLib.idle_add(self.recargar_proyectos)
        GLib.idle_add(self.mostrar_mensaje, "Creado", f"Carpeta '{nombre}' lista para usar.")

    def al_borrar_proyecto(self, btn, carpeta):
        dialogo = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="¿Eliminar Proyecto?")
        dialogo.format_secondary_text(f"¿Estás seguro de que deseas eliminar permanentemente la carpeta '{carpeta}'?\n\nEsta acción no se puede deshacer.")
        res = dialogo.run()
        dialogo.destroy()
        if res == Gtk.ResponseType.YES:
            self._lanzar_hilo(self._tarea_borrar_proyecto_bg, (carpeta,))

    def _tarea_borrar_proyecto_bg(self, carpeta):
        self.ejecutar_sudo(["rm", "-rf", os.path.join(self.dir_proyectos, carpeta)])
        GLib.idle_add(self.recargar_proyectos)
        GLib.idle_add(self.mostrar_mensaje, "Eliminado", f"La carpeta '{carpeta}' ha sido eliminada.")

    # Cargo mis preferencias guardadas si existen
    def cargar_configuracion(self):
        self.ruta_config = os.path.expanduser("~/.teto-panel-config.json")
        try:
            if os.path.exists(self.ruta_config):
                with open(self.ruta_config, "r") as f:
                    datos = json.load(f)
                    self.dir_proyectos = datos.get("project_dir", "/var/www/html")
                    self.favoritos = datos.get("favorites", [])
                    w, h = datos.get("width", 900), datos.get("height", 700)
                    self.resize(w, h)
                    if "x" in datos and "y" in datos:
                        self.move(datos["x"], datos["y"])
            else:
                self.dir_proyectos = "/var/www/html"
                self.favoritos = []
                self.set_position(Gtk.WindowPosition.CENTER)
        except Exception:
            self.dir_proyectos = "/var/www/html"
            self.favoritos = []

    # Guardar posicion y tamano de ventana
    def guardar_configuracion(self, widget, evento):
        try:
            tamano = self.get_size()
            pos = self.get_position()
            datos = {"width": tamano.width, "height": tamano.height, "x": pos.root_x, "y": pos.root_y}
            with open(self.ruta_config, "w") as f:
                datos["project_dir"] = self.dir_proyectos
                datos["favorites"] = self.favoritos
                json.dump(datos, f)
        except Exception:
            pass
        return False

    # Cuando cierro la ventana, guardo y se esconde en la bandeja
    def al_cerrar_ventana(self, widget, evento):
        self.guardar_configuracion(widget, evento)
        self.hide()
        return True

    # Crea el menú que aparece al hacer clic derecho en el icono de la bandeja
    def crear_menu_bandeja(self):
        menu = Gtk.Menu()
        item_mostrar = Gtk.MenuItem(label="Mostrar/Ocultar Panel")
        item_mostrar.connect("activate", lambda x: self.al_activar_bandeja(None))
        menu.append(item_mostrar)
        menu.append(Gtk.SeparatorMenuItem())
        for nombre, funcion in [("🚀 Iniciar Servicios", self.al_iniciar_entorno), ("💤 Detener Servicios", self.al_detener_entorno), ("📂 Abrir Proyectos", self.al_abrir_www)]:
            item = Gtk.MenuItem(label=nombre)
            item.connect("activate", funcion)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        item_salir = Gtk.MenuItem(label="❌ Cerrar Teto Panel")
        item_salir.connect("activate", self.al_salir)
        menu.append(item_salir)
        menu.show_all()
        return menu

    # Muestro u oculto la app al darle al icono
    def al_activar_bandeja(self, icono):
        if self.is_visible():
            self.hide()
        else:
            self.present()

    def al_popup_bandeja(self, icono, boton, tiempo):
        self.menu_bandeja.popup(None, None, None, None, boton, tiempo)

    def al_salir(self, menu_item):
        if self.proc_tail:
            try: self.proc_tail.terminate()
            except: pass
        Gtk.main_quit()

    # Pido la clave de sudo, valido y activo el token (sin guardar la clave)
    def autenticar_sudo(self):
        dialogo = Gtk.Dialog(title="🔑 Autenticación Teto", transient_for=self, flags=Gtk.DialogFlags.MODAL)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Desbloquear", Gtk.ResponseType.OK)
        dialogo.set_default_size(350, 150)
        
        caja = dialogo.get_content_area()
        caja_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        caja_h.set_margin_top(15); caja_h.set_margin_bottom(15); caja_h.set_margin_start(15); caja_h.set_margin_end(15)
        caja.add(caja_h)

        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(os.path.join(self.ruta_base, "teto.png"), 80, -1, True)
            caja_h.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
        except:
            caja_h.pack_start(Gtk.Label(label="🔒"), False, False, 0)

        caja_v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        caja_h.pack_start(caja_v, True, True, 0)
        
        caja_v.pack_start(Gtk.Label(label="<b>Contraseña de Administrador</b>", use_markup=True, xalign=0), False, False, 0)
        caja_v.pack_start(Gtk.Label(label="Necesaria para gestionar servicios.", xalign=0), False, False, 0)

        etiqueta_error = Gtk.Label(label="", xalign=0)
        caja_v.pack_start(etiqueta_error, False, False, 0)

        entrada = Gtk.Entry()
        entrada.set_visibility(False)
        entrada.set_activates_default(True)
        entrada.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
        entrada.connect("icon-press", lambda e, p, v: e.set_visibility(not e.get_visibility()))
        caja_v.pack_start(entrada, False, False, 5)
        
        dialogo.set_default_response(Gtk.ResponseType.OK)
        dialogo.show_all()
        
        intentos = 0
        while intentos < 3:
            respuesta = dialogo.run()
            if respuesta != Gtk.ResponseType.OK:
                break

            pwd = entrada.get_text()
            # Valido y renuevo el token de sudo (timeout por defecto 15min)
            verificacion = subprocess.run(["sudo", "-S", "-v"], input=pwd+"\n", capture_output=True, text=True)
            
            if verificacion.returncode == 0:
                dialogo.destroy()
                # Mantengo el token vivo en segundo plano cada 60s
                GLib.timeout_add_seconds(60, self._mantener_sudo_activo)
                return
            
            intentos += 1
            if intentos < 3:
                etiqueta_error.set_markup(f"<span foreground='#d32f2f'><b>Contraseña incorrecta. Intentos: {3-intentos}</b></span>")
                entrada.set_text("")
                entrada.grab_focus()
                
                base_x, base_y = dialogo.get_position()
                for i, off in enumerate([10, -10, 10, -10, 5, -5, 0]):
                    GLib.timeout_add(50 * i, lambda w=dialogo, x=base_x, y=base_y, o=off: w.move(x + o, y))

        dialogo.destroy()
        sys.exit(0)

    # Refresco el token de sudo para que no caduque mientras la app está abierta
    def _mantener_sudo_activo(self):
        # sudo -n -v actualiza la marca de tiempo si ya está autenticado, sin pedir clave
        subprocess.run(["sudo", "-n", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    # Lanzo tareas en segundo plano para no congelar la ventana
    def _lanzar_hilo(self, funcion, args=()):
        threading.Thread(target=funcion, args=args, daemon=True).start()

    # Ejecuto comandos usando el token activo de sudo (sin pasar clave en texto plano)
    def ejecutar_sudo(self, comando, **kwargs):
        # Usamos -n para no interactivo. Si el token caduca, esto fallará, 
        # pero el loop _mantener_sudo_activo debería prevenirlo.
        kwargs.setdefault("text", True)
        return subprocess.run(["sudo", "-n"] + comando, **kwargs)

    # Lanzo una ventanita de mensaje simple
    def mostrar_mensaje(self, titulo, texto):
        dialogo = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=titulo,
        )
        dialogo.format_secondary_text(texto)
        dialogo.run()
        dialogo.destroy()

    # Enciendo todo Apache, DB, Mailpit y abro VS Code
    def al_iniciar_entorno(self, btn):
        self._lanzar_hilo(self._tarea_iniciar_entorno_bg)

    def _tarea_iniciar_entorno_bg(self):
        self.ejecutar_sudo(["systemctl", "start", "apache2", "mariadb"])
        
        if subprocess.run(["pgrep", "mailpit"], stdout=subprocess.DEVNULL).returncode != 0:
            subprocess.Popen(["mailpit"], stdout=subprocess.DEVNULL)
        
        if subprocess.run(["pgrep", "code"], stdout=subprocess.DEVNULL).returncode != 0:
            subprocess.Popen(["code", self.dir_proyectos])
        
        subprocess.Popen(["xdg-open", "http://localhost"])
        
        ruta_nav = os.path.expanduser("~/AppImages/navicat_premium_lite_17.appimage")
        if subprocess.run(["pgrep", "-f", "navicat"], stdout=subprocess.DEVNULL).returncode != 0:
            if os.path.exists(ruta_nav):
                subprocess.Popen([ruta_nav], stdout=subprocess.DEVNULL)

    # Apago todo lo que encendí, pero me quedo abierto por si acaso
    def al_detener_entorno(self, btn):
        self._lanzar_hilo(self._tarea_detener_entorno_bg)

    def _tarea_detener_entorno_bg(self):
        self.ejecutar_sudo(["systemctl", "stop", "apache2", "mariadb"])
        subprocess.run(["pkill", "mailpit"])
        subprocess.run(["pkill", "code"])
        GLib.idle_add(self.actualizar_estado)

    def al_reiniciar_servicios(self, btn):
        self._lanzar_hilo(self._tarea_reiniciar_servicios_bg)

    def _tarea_reiniciar_servicios_bg(self):
        self.ejecutar_sudo(["systemctl", "restart", "apache2", "mariadb"])
        GLib.idle_add(self.actualizar_estado)
        GLib.idle_add(self.mostrar_mensaje, "Servicios", "Apache y MariaDB reiniciados.")

    # Abro la carpeta de proyectos en el explorador
    def al_abrir_www(self, btn):
        subprocess.Popen(["xdg-open", self.dir_proyectos])

    # Analiza el log de errores y muestra un resumen estadístico
    def al_analizar_logs(self, btn):
        self._lanzar_hilo(self._tarea_analizar_logs_bg)

    def _tarea_analizar_logs_bg(self):
        # Leemos las últimas 2000 líneas del log de errores
        res = self.ejecutar_sudo(["tail", "-n", "2000", "/var/log/apache2/error.log"], capture_output=True)
        if res.returncode != 0:
            GLib.idle_add(self.mostrar_mensaje, "Error", "No se pudo leer el log de Apache.")
            return

        texto = res.stdout
        stats = {
            "PHP Fatal": texto.count("PHP Fatal error"),
            "PHP Warning": texto.count("PHP Warning"),
            "PHP Parse": texto.count("PHP Parse error"),
            "DB Error": texto.count("SQLSTATE") + texto.count("Connection refused")
        }
        
        # Extraemos mensajes únicos recientes (para no repetir spam)
        lineas = texto.splitlines()
        errores_unicos = []
        vistos = set()
        
        for l in reversed(lineas):
            if "PHP" in l or "SQL" in l or "error" in l.lower():
                # Limpiamos timestamp para agrupar por mensaje real
                msg = l.split("]")[-1].strip() if "]" in l else l
                if msg not in vistos:
                    errores_unicos.append(msg[:85] + "..." if len(msg)>85 else msg)
                    vistos.add(msg)
                if len(errores_unicos) >= 6: break
        
        informe = "<b>🔍 Resumen de Salud (Últimas 2000 líneas):</b>\n\n"
        informe += f"🛑 Errores Fatales: <span foreground='#ff5252'><b>{stats['PHP Fatal']}</b></span>\n"
        informe += f"⚠️ Advertencias PHP: <span foreground='#ffb74d'><b>{stats['PHP Warning']}</b></span>\n"
        informe += f"🐛 Errores Sintaxis: <span foreground='#ff5252'><b>{stats['PHP Parse']}</b></span>\n"
        informe += f"🐬 Errores DB: <span foreground='#42a5f5'><b>{stats['DB Error']}</b></span>\n\n"
        informe += "<b>🕒 Últimos eventos detectados:</b>\n" + ("\n".join(f"• <small>{e}</small>" for e in errores_unicos) if errores_unicos else "• <i>No se encontraron errores relevantes.</i>")
        
        GLib.idle_add(self._mostrar_reporte_logs, informe)

    def _mostrar_reporte_logs(self, markup):
        dialogo = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text="Análisis de Logs")
        dialogo.format_secondary_markup(markup)
        dialogo.run()
        dialogo.destroy()

    # Borro cachés de RAM para liberar memoria
    def al_optimizar_ram(self, btn):
        self._lanzar_hilo(self._tarea_optimizar_ram_bg)

    def _tarea_optimizar_ram_bg(self):
        self.ejecutar_sudo(["sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"])

    # Abro el cliente de correo local
    def al_abrir_mailpit(self, btn):
        subprocess.Popen(["xdg-open", "http://localhost:8025"])

    # Cambio la versión de PHP
    def al_cambiar_php(self, btn):
        versiones = sorted(glob.glob("/usr/bin/php[0-9].[0-9]"))
        if not versiones:
            self.mostrar_mensaje("Error", "No se encontraron versiones de PHP en /usr/bin/")
            return

        dialogo = Gtk.Dialog(title="Cambiar Versión PHP", transient_for=self, flags=0)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Aplicar", Gtk.ResponseType.OK)
        dialogo.set_default_size(300, 120)
        
        caja = dialogo.get_content_area()
        caja.set_spacing(10)
        caja.set_border_width(20)
        
        caja.add(Gtk.Label(label="Selecciona la versión a utilizar (CLI y Apache):"))
        
        combo = Gtk.ComboBoxText()
        for v in versiones:
            combo.append_text(os.path.basename(v))
        combo.set_active(0)
        caja.add(combo)
        
        dialogo.show_all()
        respuesta = dialogo.run()
        
        if respuesta == Gtk.ResponseType.OK:
            seleccionado = combo.get_active_text()
            dialogo.destroy()
            self._lanzar_hilo(self._tarea_cambiar_php_bg, (seleccionado,))
        else:
            dialogo.destroy()

    def _tarea_cambiar_php_bg(self, seleccionado):
        cmd = (f"for mod in /etc/apache2/mods-enabled/php*.load; do a2dismod $(basename $mod .load); done; "
               f"a2enmod {seleccionado}; "
               f"update-alternatives --set php /usr/bin/{seleccionado}; "
               f"systemctl restart apache2")
        
        self.ejecutar_sudo(["sh", "-c", cmd])
        GLib.idle_add(self.actualizar_estado)
        GLib.idle_add(self.mostrar_mensaje, "PHP Cambiado", f"El sistema ahora usa {seleccionado}")

    # Abro las opciones para cambiar la carpeta raíz
    def al_abrir_ajustes(self, btn):
        dialogo = Gtk.Dialog(title="Configuración Teto Panel", transient_for=self, flags=0)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Guardar y Aplicar", Gtk.ResponseType.OK)
        dialogo.set_default_size(400, 150)
        
        caja = dialogo.get_content_area()
        caja.set_spacing(10)
        caja.set_border_width(20)
        
        caja.add(Gtk.Label(label="Carpeta raíz de proyectos (localhost):", xalign=0))
        
        selector = Gtk.FileChooserButton(title="Seleccionar Carpeta", action=Gtk.FileChooserAction.SELECT_FOLDER)
        selector.set_current_folder(self.dir_proyectos)
        caja.add(selector)
        
        caja.add(Gtk.Label(label="⚠️ Al cambiar esto, Apache se reconfigurará.", xalign=0))
        
        expander = Gtk.Expander(label="Don-Gato700")
        scroll_txt = Gtk.ScrolledWindow()
        scroll_txt.set_min_content_height(150)
        vista_txt = Gtk.TextView()
        vista_txt.set_editable(False)
        vista_txt.set_cursor_visible(False)
        vista_txt.set_wrap_mode(Gtk.WrapMode.WORD)
        
        ruta_readme = os.path.join(self.ruta_base, "readme.txt")
        contenido = "Crea un archivo 'readme.txt' en la carpeta de la aplicación para ver su contenido aquí."
        if os.path.exists(ruta_readme):
            try: 
                with open(ruta_readme, "r", encoding="utf-8") as f: contenido = f.read()
            except: pass
            
        vista_txt.get_buffer().set_text(contenido)
        scroll_txt.add(vista_txt)
        expander.add(scroll_txt)
        caja.add(expander)

        dialogo.show_all()
        respuesta = dialogo.run()
        
        if respuesta == Gtk.ResponseType.OK:
            nuevo_dir = selector.get_filename()
            dialogo.destroy()
            
            if nuevo_dir and nuevo_dir != self.dir_proyectos:
                rutas_criticas = [os.path.expanduser("~"), "/", "/etc", "/usr", "/var", "/bin", "/sbin", "/lib", "/root", "/boot", "/opt"]
                if nuevo_dir in rutas_criticas:
                    advertencia = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.WARNING,
                                             buttons=Gtk.ButtonsType.YES_NO, text="⚠️ ¡Advertencia de Seguridad!")
                    advertencia.format_secondary_text(f"Has seleccionado una carpeta crítica del sistema:\n'{nuevo_dir}'\n\n"
                                               "Esto expondrá TODOS los archivos de esta ubicación al servidor web y modificará sus permisos de lectura/escritura.\n\n"
                                               "¿Estás completamente seguro de continuar?")
                    res = advertencia.run()
                    advertencia.destroy()
                    if res != Gtk.ResponseType.YES:
                        return

                self.dir_proyectos = nuevo_dir
                self.etiqueta_proyectos.set_markup(f"<b>📂 Proyectos ({self.dir_proyectos})</b>")
                self.guardar_configuracion(None, None)
                self.recargar_proyectos()
                self._lanzar_hilo(self._tarea_guardar_ajustes_bg)
        else:
            dialogo.destroy()

    def _tarea_guardar_ajustes_bg(self):
        contenido_conf = (f"<VirtualHost *:80>\n"
                        f"    ServerAdmin webmaster@localhost\n"
                        f"    DocumentRoot \"{self.dir_proyectos}\"\n"
                        f"    <Directory \"{self.dir_proyectos}\">\n"
                        f"        Options Indexes FollowSymLinks\n"
                        f"        AllowOverride All\n"
                        f"        Require all granted\n"
                        f"    </Directory>\n"
                        f"    ErrorLog ${{APACHE_LOG_DIR}}/error.log\n"
                        f"    CustomLog ${{APACHE_LOG_DIR}}/access.log combined\n"
                        f"</VirtualHost>")
        
        archivo_tmp = "/tmp/000-default.conf"
        with open(archivo_tmp, "w") as f: f.write(contenido_conf)
        
        try: usuario = pwd.getpwuid(os.getuid()).pw_name
        except: usuario = "www-data"

        cmd = (f"mv {archivo_tmp} /etc/apache2/sites-available/000-default.conf; "
               f"a2ensite 000-default.conf; "
               f"chown -R {usuario}:{usuario} '{self.dir_proyectos}'; "
               f"chmod 755 '{self.dir_proyectos}'; "
               f"p='{self.dir_proyectos}'; "
               f"while [ \"$p\" != \"/\" ] && [ \"$p\" != \".\" ]; do chmod +x \"$p\"; p=$(dirname \"$p\"); done; "
               f"systemctl restart apache2")
        self.ejecutar_sudo(["sh", "-c", cmd])
        GLib.idle_add(self.mostrar_mensaje, "Configuración Actualizada", f"Localhost ahora apunta a:\n{self.dir_proyectos}")

    # --- Funciones de Saneamiento y Borrado ---

    def al_sanear_apache(self, btn):
        self.mostrar_mensaje("Sanear Apache", "Se buscarán configuraciones rotas y se reseteará Apache si es necesario.")
        self._lanzar_hilo(self.sanear_apache)

    def sanear_apache(self):
        resultado = self.ejecutar_sudo(["apachectl", "-t"], capture_output=True)
        
        if "AH00112" in resultado.stderr or "Syntax error" in resultado.stderr:
            self.ejecutar_sudo(["sh", "-c", "a2dissite *.conf && a2ensite 000-default.conf"])
            self.ejecutar_sudo(["systemctl", "restart", "apache2"])
            GLib.idle_add(self.mostrar_mensaje, "Apache Saneado", "Se detectaron errores. Se han desactivado los sitios rotos y reiniciado Apache.")
        else:
            GLib.idle_add(self.mostrar_mensaje, "Apache OK", "La configuración de Apache es correcta. No se requieren acciones.")

    # Configuro un nuevo dominio local con VirtualHost
    def al_crear_vhost(self, btn):
        dialogo = Gtk.Dialog(title="Nuevo Virtual Host", transient_for=self, flags=0)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Crear", Gtk.ResponseType.OK)
        dialogo.set_default_size(350, 220)
        
        rejilla = Gtk.Grid(column_spacing=10, row_spacing=15, margin=20)
        
        entrada_dominio = Gtk.Entry()
        entrada_dominio.set_placeholder_text("ejemplo.test")
        entrada_dir = Gtk.Entry()
        entrada_dir.set_placeholder_text("nombre-carpeta")
        check_ssl = Gtk.CheckButton(label="Habilitar SSL (https://)")
        
        rejilla.attach(Gtk.Label(label="Dominio:", xalign=0), 0, 0, 1, 1)
        rejilla.attach(entrada_dominio, 1, 0, 1, 1)
        rejilla.attach(Gtk.Label(label="Carpeta en WWW:", xalign=0), 0, 1, 1, 1)
        rejilla.attach(entrada_dir, 1, 1, 1, 1)
        rejilla.attach(check_ssl, 1, 2, 1, 1)
        
        dialogo.get_content_area().add(rejilla)
        dialogo.show_all()
        
        if dialogo.run() == Gtk.ResponseType.OK:
            dominio = entrada_dominio.get_text().strip()
            carpeta = entrada_dir.get_text().strip()
            usar_ssl = check_ssl.get_active()
            dialogo.destroy()
            
            if not dominio or not carpeta:
                self.mostrar_mensaje("Error", "Debes completar ambos campos.")
                return
            
            ruta_destino = os.path.join(self.dir_proyectos, carpeta)
            if not os.path.exists(ruta_destino):
                self.mostrar_mensaje("Error", f"La carpeta '{carpeta}' no existe en {self.dir_proyectos}.\n\nPor favor crea la carpeta primero o verifica el nombre.")
                return
            
            self._lanzar_hilo(self._tarea_crear_vhost_bg, (dominio, carpeta, usar_ssl))
        else:
            dialogo.destroy()

    def _tarea_crear_vhost_bg(self, dominio, carpeta, usar_ssl):
        conf = (f"<VirtualHost *:80>\n"
                f"    ServerName {dominio}\n"
                f"    DocumentRoot \"{self.dir_proyectos}/{carpeta}\"\n"
                f"    <Directory \"{self.dir_proyectos}/{carpeta}\">\n"
                f"        AllowOverride All\n"
                f"        Require all granted\n"
                f"    </Directory>\n"
                f"</VirtualHost>")

        cmd_ssl = ""
        if usar_ssl:
            conf += (f"\n<VirtualHost *:443>\n"
                     f"    ServerName {dominio}\n"
                     f"    DocumentRoot \"{self.dir_proyectos}/{carpeta}\"\n"
                     f"    SSLEngine on\n"
                     f"    SSLCertificateFile /etc/ssl/certs/{dominio}.crt\n"
                     f"    SSLCertificateKeyFile /etc/ssl/private/{dominio}.key\n"
                     f"    <Directory \"{self.dir_proyectos}/{carpeta}\">\n"
                     f"        AllowOverride All\n"
                     f"        Require all granted\n"
                     f"    </Directory>\n"
                     f"</VirtualHost>")
            
            cmd_ssl = (f"openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
                       f"-keyout /etc/ssl/private/{dominio}.key "
                       f"-out /etc/ssl/certs/{dominio}.crt "
                       f"-subj '/C=US/ST=Dev/L=Local/O=TetoPanel/CN={dominio}'; "
                       f"a2enmod ssl; ")

        archivo_tmp = f"/tmp/{dominio}.conf"
        with open(archivo_tmp, "w") as f: f.write(conf)
        
        cmd = (f"{cmd_ssl}"
               f"mv {archivo_tmp} /etc/apache2/sites-available/{dominio}.conf; "
               f"mkdir -p {self.dir_proyectos}/{carpeta}; "
               f"chown -R $SUDO_USER:$SUDO_USER {self.dir_proyectos}/{carpeta}; "
               f"chmod -R 775 {self.dir_proyectos}/{carpeta}; "
               f"a2ensite {dominio}.conf; "
               f"grep -q '{dominio}' /etc/hosts || echo '127.0.0.1 {dominio}' >> /etc/hosts; "
               f"systemctl reload apache2")
        
        self.ejecutar_sudo(["sh", "-c", cmd])
        GLib.idle_add(self.mostrar_mensaje, "Éxito", f"Host {dominio} creado {'con SSL ' if usar_ssl else ''}y activado.")
        GLib.idle_add(self.recargar_proyectos)

    def al_borrar_vhost(self, btn):
        dialogo = Gtk.Dialog(title="Eliminar Virtual Host", transient_for=self, flags=0)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "ELIMINAR", Gtk.ResponseType.OK)
        dialogo.set_default_size(300, 150)
        
        caja = dialogo.get_content_area()
        caja.set_spacing(10); caja.set_border_width(20)
        caja.add(Gtk.Label(label="Selecciona el dominio a eliminar:"))
        
        combo = Gtk.ComboBoxText()
        sitios_encontrados = False
        
        try:
            for ruta in sorted(glob.glob("/etc/apache2/sites-available/*.conf")):
                nombre = os.path.basename(ruta).replace(".conf", "")
                if nombre not in ["000-default", "default-ssl"]:
                    combo.append_text(nombre)
                    sitios_encontrados = True
        except Exception: pass
        
        if sitios_encontrados:
            combo.set_active(0)
        else:
            combo.append_text("(No hay sitios personalizados)")
            combo.set_active(0)
            combo.set_sensitive(False)
            dialogo.set_response_sensitive(Gtk.ResponseType.OK, False)

        caja.add(combo)
        caja.add(Gtk.Label(label="⚠️ Esto borrará la configuración de Apache,\npero NO borrará los archivos del proyecto."))
        
        dialogo.show_all()
        if dialogo.run() == Gtk.ResponseType.OK:
            dominio = combo.get_active_text()
            dialogo.destroy()
            if dominio and sitios_encontrados:
                self._lanzar_hilo(self._tarea_borrar_vhost_bg, (dominio,))
        else:
            dialogo.destroy()

    def _tarea_borrar_vhost_bg(self, dominio):
        # 1. Desactivar el sitio
        self.ejecutar_sudo(["a2dissite", f"{dominio}.conf"])
        # 2. Borrar archivo conf
        self.ejecutar_sudo(["rm", "-f", f"/etc/apache2/sites-available/{dominio}.conf"])
        # 3. Limpiar hosts
        self.ejecutar_sudo(["sed", "-i", f"/{dominio}/d", "/etc/hosts"])
        # 4. Reiniciar
        self.ejecutar_sudo(["systemctl", "restart", "apache2"])
        GLib.idle_add(self.actualizar_estado)
        GLib.idle_add(self.mostrar_mensaje, "Eliminado", f"VHost {dominio} eliminado correctamente.")

    # Cambio la clave root de la base de datos
    def al_cambiar_clave_db(self, btn):
        dialogo = Gtk.Dialog(title="Cambiar Clave MariaDB", transient_for=self, flags=0)
        dialogo.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Cambiar", Gtk.ResponseType.OK)
        dialogo.set_default_size(300, 150)
        
        caja = dialogo.get_content_area()
        caja.set_spacing(10)
        caja.set_border_width(20)
        
        caja.add(Gtk.Label(label="Nueva contraseña para root@localhost:"))
        
        entrada_clave = Gtk.Entry()
        entrada_clave.set_visibility(False)  
        caja.add(entrada_clave)
        
        dialogo.show_all()
        
        if dialogo.run() == Gtk.ResponseType.OK:
            nueva_clave = entrada_clave.get_text()
            dialogo.destroy()
            self._lanzar_hilo(self._tarea_cambiar_clave_db_bg, (nueva_clave,))
        else:
            dialogo.destroy()

    def _tarea_cambiar_clave_db_bg(self, nueva_clave):
        clave_segura = nueva_clave.replace("'", "\\'")
        cmd = f"mysql -e \"ALTER USER 'root'@'localhost' IDENTIFIED BY '{clave_segura}'; FLUSH PRIVILEGES;\""
        self.ejecutar_sudo(["sh", "-c", cmd])
        GLib.idle_add(self.mostrar_mensaje, "Éxito", "Clave de base de datos actualizada.")

    # Hago un ping a la DB a ver si responde
    def al_probar_conexion_db(self, btn):
        self._lanzar_hilo(self._tarea_probar_conexion_db_bg)

    def _tarea_probar_conexion_db_bg(self):
        res = self.ejecutar_sudo(["mysqladmin", "ping"], capture_output=True)
        if res.returncode == 0:
            GLib.idle_add(self.mostrar_mensaje, "Conexión Exitosa", f"MariaDB está operativa y respondiendo:\n{res.stdout.strip()}")
        else:
            GLib.idle_add(self.mostrar_mensaje, "Sin Conexión", f"No se pudo conectar a la base de datos.\nError: {res.stderr.strip()}")

    # Muestro menú copiar en la terminal embebida
    def al_clic_terminal(self, widget, evento):
        if evento.button == 3:
            menu = Gtk.Menu()
            item = Gtk.MenuItem(label="Copiar")
            item.connect("activate", lambda x: widget.copy_clipboard_format(Vte.Format.TEXT))
            menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, None, evento.button, evento.time)
            return True
        return False

    # Lanzo una terminal de verdad aparte
    def al_abrir_terminal_externa(self, btn):
        try:
            subprocess.Popen(["x-terminal-emulator"], cwd=self.dir_proyectos)
        except FileNotFoundError:
            self.mostrar_mensaje("Error", "No se encontró un emulador de terminal (x-terminal-emulator).")

    # Easter egg: Reproduzco el audio de Teto
    def al_reproducir_teto(self, widget, evento):
        if self.reproductor_teto and self.reproductor_teto.poll() is None:
            return

        mp3 = os.path.join(self.ruta_base, "teto.mp3")
        if not os.path.exists(mp3): return
        
        for cmd in [["ffplay", "-nodisp", "-autoexit"], ["mpv", "--no-video"], ["mpg123"], ["cvlc", "--play-and-exit", "--no-video"]]:
            try:
                self.reproductor_teto = subprocess.Popen(cmd + [mp3], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError: continue

if __name__ == "__main__":
    ventana = PanelTeto()
    ventana.connect("destroy", Gtk.main_quit)
    ventana.show_all()
    Gtk.main()