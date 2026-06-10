import flet as ft
import flet_charts as charts
import os
import sys
import hashlib
import csv
import asyncio
import time
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from debug_helper import init_debugger, safe_call, safe_async

# ==================== CONFIGURACIÓN DE COLORES ====================
class AppColors:
    DARK = {
        "primary": "#4f46e5",
        "bg": "#0f172a",
        "surface": "#1e293b",
        "text": "#f8fafc",
        "text_secondary": "#94a3b8",
        "error": "#f43f5e",
        "success": "#10b981"
    }
    LIGHT = {
        "primary": "#4f46e5",
        "bg": "#ffffff",
        "surface": "#f1f5f9",
        "text": "#0f172a",
        "text_secondary": "#64748b",
        "error": "#dc2626",
        "success": "#16a34a"
    }

    @staticmethod
    def get(mode: ft.ThemeMode):
        return AppColors.DARK if mode == ft.ThemeMode.DARK else AppColors.LIGHT

# ==================== INICIALIZACIÓN DE SUPABASE ====================
supabase: Client = None
columna_principal = ft.Column(expand=True, alignment=ft.MainAxisAlignment.START)

def inicializar_supabase(url, key):
    global supabase
    if not url or not key:
        print("❌ ERROR CRÍTICO: No se encontraron las variables de entorno SUPABASE_URL o SUPABASE_KEY")
        return
    try:
        supabase = create_client(url, key)
        print("✓ Cliente Supabase conectado de forma exitosa.")
    except Exception as e:
        print(f"Error al conectar a Supabase: {e}")

# ==================== DIAGNÓSTICO DE INFRAESTRUCTURA ====================
def verificar_y_guia_configuracion(page):
    global supabase
    if supabase is None:
        mostrar_snackbar(page, "Error: Cliente Supabase no inicializado.", AppColors.DARK["error"])
        return False
    problemas = []
    try:
        supabase.table("categorias").select("count", count="exact").limit(0).execute()
    except Exception as e:
        if "does not exist" in str(e).lower():
            problemas.append("""
CREATE TABLE categorias (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL,
  icono TEXT DEFAULT 'shopping_cart',
  user_id UUID NOT NULL
);""")
    try:
        supabase.table("gastos").select("categoria_id").limit(1).execute()
    except Exception as e:
        if "column" in str(e).lower() and "does not exist" in str(e).lower():
            problemas.append("ALTER TABLE gastos ADD COLUMN categoria_id INT REFERENCES categorias(id);")
    try:
        supabase.table("presupuestos").select("count", count="exact").limit(0).execute()
    except Exception:
        problemas.append("""
CREATE TABLE presupuestos (
  id SERIAL PRIMARY KEY,
  categoria_id INT REFERENCES categorias(id),
  limite REAL NOT NULL,
  user_id UUID NOT NULL,
  UNIQUE(categoria_id, user_id)
);""")
    if problemas:
        contenido_sql = "\n\n".join(problemas)
        page.dialog = ft.AlertDialog(
            title=ft.Text(value="⚙️ Configuración inicial requerida", color=AppColors.DARK["primary"]),
            content=ft.Column([
                ft.Text(value="Ejecuta el SQL requerido en tu consola de Supabase y reinicia la app.", size=14),
                ft.Container(content=ft.Text(value=contenido_sql, selectable=True, size=12, font_family="monospace"), bgcolor="#2d2d2d", padding=10, border_radius=8)
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton(text="Entendido", on_click=lambda e: safe_call(close_dialog, page)())],
        )
        page.dialog.open = True
        page.update()
        return False
    return True

def close_dialog(page):
    if page.dialog:
        page.dialog.open = False
        page.update()

def mostrar_snackbar(page, mensaje, color):
    page.snack_bar = ft.SnackBar(ft.Text(mensaje), bgcolor=color)
    page.snack_bar.open = True
    page.update()

# ==================== CONFIGURACIÓN DE RUTA SEGURA ====================
def get_secure_pin_path() -> str:
    """Devuelve la ruta donde se guardará el PIN, usando una carpeta oculta del sistema."""
    base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    app_dir = os.path.join(base_dir, "MoneyFlow")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return os.path.join(app_dir, "pin_hash.txt")

# ==================== SEGURIDAD DEL PIN (PBKDF2 + bloqueo) ====================
def generar_salt():
    return os.urandom(16).hex()

def hash_pin_seguro(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', pin.encode(), salt.encode(), 100000).hex()

def save_pin_hash(pin: str):
    salt = generar_salt()
    hash_val = hash_pin_seguro(pin, salt)
    try:
        with open(get_secure_pin_path(), "w") as f:
            f.write(f"{salt}:{hash_val}")
    except Exception as e:
        print(f"Error al guardar PIN: {e}")

def load_pin_hash():
    ruta_pin = get_secure_pin_path()
    if os.path.exists(ruta_pin):
        try:
            with open(ruta_pin, "r") as f:
                data = f.read().strip().split(":")
                if len(data) == 2:
                    return data[0], data[1]
        except Exception:
            return None, None
    return None, None

# ==================== PANTALLA DE PIN ====================
def solicitar_pin(page, on_correct_pin):
    colors = AppColors.get(page.theme_mode)
    page.bgcolor = colors["bg"]
    
    pin_input = ft.TextField(
        label="PIN de acceso",
        password=True,
        can_reveal_password=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        max_length=4,
        width=150,
        text_align=ft.TextAlign.CENTER,
        border_radius=16,
        bgcolor=colors["surface"],
        color=colors["text"],
    )
    error_text = ft.Text(value="", color=colors["error"])
    salt, saved_hash = load_pin_hash()
    intentos_fallidos = 0
    bloqueado_hasta = 0

    def verificar(e):
        nonlocal intentos_fallidos, bloqueado_hasta
        if time.time() < bloqueado_hasta:
            segundos = int(bloqueado_hasta - time.time())
            error_text.value = f"Demasiados intentos. Espera {segundos}s."
            page.update()
            return

        entered = pin_input.value.strip()
        if not entered or len(entered) != 4:
            error_text.value = "Ingresa un PIN de 4 dígitos"
            page.update()
            return

        if saved_hash is None:
            save_pin_hash(entered)
            mostrar_snackbar(page, "PIN configurado correctamente", colors["success"])
            on_correct_pin()
        elif hash_pin_seguro(entered, salt) == saved_hash:
            intentos_fallidos = 0
            on_correct_pin()
        else:
            intentos_fallidos += 1
            if intentos_fallidos >= 3:
                bloqueado_hasta = time.time() + 30
                error_text.value = "Bloqueado por seguridad. Espera 30s."
            else:
                error_text.value = f"PIN incorrecto ({intentos_fallidos}/3 intentos)"
            pin_input.value = ""
            page.update()

    vista_pin = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.LOCK_ROUNDED, size=40, color=colors["primary"]),
            ft.Text(value="🔐 Enhorabuena - Ingresa tu PIN", size=24, weight="bold", color=colors["primary"]),
            ft.Text(value="Protege tu información financiera", size=14, color=colors["text_secondary"]),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            pin_input,
            ft.FilledButton(
                content=ft.Text("Acceder", color="white"),
                on_click=lambda e: safe_call(verificar, e)(),
                style=ft.ButtonStyle(bgcolor=colors["primary"])
            ),
            error_text,
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
        padding=20, 
        expand=True
    )

    page.controls.clear()
    page.appbar = None
    page.add(vista_pin)
    page.update()

# ==================== LOGIN ====================
def login_view(page: ft.Page):
    colors = AppColors.get(page.theme_mode)
    page.bgcolor = colors["bg"]
    page.appbar = None
    page.navigation_bar = None
    
    email_input = ft.TextField(label="Correo Electrónico", border_color=colors["primary"], color=colors["text"])
    password_input = ft.TextField(label="Contraseña", password=True, can_reveal_password=True, border_color=colors["primary"], color=colors["text"])
    error_text = ft.Text(value="", color=colors["error"])

    def do_login(e):
        global supabase
        if supabase is None:
            error_text.value = "Error: El cliente no está inicializado."
            page.update()
            return
        try:
            e.control.disabled = True
            page.update()
            res = supabase.auth.sign_in_with_password({"email": email_input.value, "password": password_input.value})
            if res and res.user:
                page.user_id = res.user.id
                solicitar_pin(page, lambda: mostrar_interfaz_principal(page))
            else:
                error_text.value = "No se pudo obtener la sesión del usuario."
                e.control.disabled = False
                page.update()
        except Exception as err:
            print(f"\n❌ [ERROR DETECTADO EN LOGIN]: {str(err)}\n")
            error_text.value = "Error de autenticación. Verifica tus datos o tu conexión."
            e.control.disabled = False
            page.update()

    vista_login = ft.Container(
        content=ft.Column([
            ft.Text("MoneyFlow - Iniciar Sesión", size=28, weight="bold", color=colors["primary"]),
            email_input, 
            password_input,
            ft.FilledButton(
                "Ingresar",
                on_click=lambda e: safe_call(do_login, e)(),
                style=ft.ButtonStyle(bgcolor=colors["primary"], color="white")
            ),
            error_text
        ], spacing=15, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=30,
        expand=True
    )

    page.controls.clear()
    page.add(vista_login)
    page.update()

# ==================== FUNCIONES DE LICENCIA ====================
async def obtener_plan(page: ft.Page) -> str:
    try:
        res = supabase.table("profiles").select("plan").eq("user_id", page.user_id).single().execute()
        return res.data.get("plan", "free") if res.data else "free"
    except Exception:
        return "free"

def mostrar_banner_limite(page: ft.Page, container_banner: ft.Container, mensaje: str):
    container_banner.content = ft.Row([
        ft.Icon(ft.Icons.LOCK, color=ft.Colors.ORANGE),
        ft.Text(mensaje, size=14, color=ft.Colors.ORANGE, expand=True),
        ft.TextButton("Activar licencia", on_click=lambda e: safe_call(mostrar_dialogo_activacion, page)()),
        # Si tienes enlace de pago, descomenta la siguiente línea:
        # ft.TextButton("Comprar ($10)", on_click=lambda e: page.launch_url("https://paypal.me/tuusuario/10")),
    ])
    container_banner.visible = True
    page.update()

def ocultar_banner_limite(page: ft.Page, container_banner: ft.Container):
    container_banner.visible = False
    page.update()

def mostrar_dialogo_activacion(page: ft.Page):
    colors = AppColors.get(page.theme_mode)
    email = ""
    try:
        user = supabase.auth.get_user()
        email = user.user.email if user and user.user else ""
    except Exception:
        pass

    codigo_input = ft.TextField(
        label="Código de activación",
        hint_text="Ej. MF-ABCD1234EFGH",
        border_color=colors["primary"],
        color=colors["text"],
        autofocus=True,
        text_align=ft.TextAlign.CENTER
    )
    error_text = ft.Text("", color=colors["error"])
    progress = ft.ProgressBar(visible=False, width=200, color=colors["primary"])

    async def activar_click(e):
        error_text.value = ""
        progress.visible = True
        page.update()
        
        codigo = codigo_input.value.strip()
        if not codigo:
            error_text.value = "Ingresa un código."
            progress.visible = False
            page.update()
            return
        
        try:
            result = supabase.rpc("activate_license", {"p_email": email, "p_code": codigo}).execute()
            if result.data:
                mostrar_snackbar(page, "🎉 ¡Licencia activada! Ya tienes acceso ilimitado.", colors["success"])
                dlg.open = False
                page.update()
            else:
                error_text.value = "Código inválido o ya usado."
        except Exception as ex:
            error_text.value = f"Error al validar: {ex}"
        finally:
            progress.visible = False
            page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("🔒 Activar Licencia", color=colors["primary"]),
        content=ft.Column([
            ft.Text(f"Email: {email}", size=12, color=colors["text_secondary"]),
            ft.Text("Ingresa el código que recibiste al comprar tu licencia.", size=14, color=colors["text"]),
            codigo_input,
            progress,
            error_text
        ], spacing=15, tight=True),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page)),
            ft.FilledButton("Activar", on_click=lambda e: safe_call(activar_click, e)()),
        ],
    )
    page.dialog = dlg
    dlg.open = True
    page.update()

# ==================== CACHÉ Y TEMPORIZADOR ====================
_cache_dashboard = {"timestamp": 0, "data": None}
_timer_dashboard = None

def cancelar_timer_dashboard():
    global _timer_dashboard
    if _timer_dashboard and not _timer_dashboard.done():
        _timer_dashboard.cancel()

# ==================== DASHBOARD CON CACHÉ Y PRESUPUESTOS ====================
def ejecutar_vista_dashboard(page: ft.Page):
    global columna_principal, supabase, _timer_dashboard
    cancelar_timer_dashboard()
    colors = AppColors.get(page.theme_mode)
    columna_principal.controls.clear()

    lbl_balance = ft.Text("$0.00", size=24, weight="bold", color="white")
    lbl_ingresos = ft.Text("$0.00", size=20, weight="bold", color="white")
    lbl_gastos = ft.Text("$0.00", size=20, weight="bold", color="white")
    grafico_container = ft.Container(height=220, alignment=ft.Alignment.CENTER)
    lista_leyendas = ft.Column(spacing=5, alignment=ft.MainAxisAlignment.CENTER)
    indicador_carga = ft.ProgressBar(width=200, color=colors["primary"], visible=False)
    alerta_presupuesto = ft.Text("", color=colors["error"], visible=False)
    presupuestos_column = ft.Column(spacing=5)

    btn_refrescar = ft.IconButton(
        icon=ft.Icons.REFRESH,
        icon_color=colors["primary"],
        tooltip="Actualizar ahora",
        on_click=lambda e: safe_call(actualizar_dashboard, True)()
    )

    def crear_kpi_card(titulo, control_texto, icon, color_inicio, color_fin):
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color="white", size=20), ft.Text(titulo, color="white70", size=12, weight="w500")]),
                control_texto
            ], spacing=5, alignment=ft.MainAxisAlignment.CENTER),
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=[color_inicio, color_fin]),
            padding=15,
            border_radius=16,
            expand=True,
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=4, color="black12")
        )

    card_balance = crear_kpi_card("Balance Neto", lbl_balance, ft.Icons.ACCOUNT_BALANCE_WALLET, "#4f46e5", "#3730a3")
    card_ingresos = crear_kpi_card("Ingresos Totales", lbl_ingresos, ft.Icons.ARROW_UPWARD_ROUNDED, "#10b981", "#065f46")
    card_gastos = crear_kpi_card("Gastos Acumulados", lbl_gastos, ft.Icons.ARROW_DOWNWARD_ROUNDED, "#f43f5e", "#9f1239")

    row_kpis = ft.ResponsiveRow([
        ft.Container(content=card_balance, col={"xs": 12, "md": 4}),
        ft.Container(content=card_ingresos, col={"xs": 12, "sm": 6, "md": 4}),
        ft.Container(content=card_gastos, col={"xs": 12, "sm": 6, "md": 4}),
    ], run_spacing=10)

    def actualizar_dashboard(forzar=False):
        global _cache_dashboard
        ahora = time.time()
        if not forzar and (ahora - _cache_dashboard["timestamp"] < 30):
            datos = _cache_dashboard["data"]
        else:
            indicador_carga.visible = True
            page.update()
            try:
                raw_datos = supabase.table("gastos").select("*").eq("user_id", page.user_id).execute()
                movimientos = raw_datos.data or []
            except Exception:
                movimientos = []
                mostrar_snackbar(page, "Error al sincronizar Dashboard con Supabase.", colors["error"])
            datos = movimientos
            _cache_dashboard["timestamp"] = ahora
            _cache_dashboard["data"] = movimientos
            indicador_carga.visible = False

        total_ingresos = 0.0
        total_gastos = 0.0
        gastos_por_categoria = {}

        for m in datos:
            try: monto = float(m.get("monto", 0) or 0)
            except ValueError: monto = 0.0

            tipo = m.get("tipo", "gasto")
            if tipo == "ingreso":
                total_ingresos += monto
            else:
                total_gastos += monto
                cat_id = str(m.get("categoria_id"))
                gastos_por_categoria[cat_id] = gastos_por_categoria.get(cat_id, 0.0) + monto

        balance_neto = total_ingresos - total_gastos
        lbl_balance.value = f"${balance_neto:,.2f}"
        lbl_ingresos.value = f"${total_ingresos:,.2f}"
        lbl_gastos.value = f"${total_gastos:,.2f}"

        grafico_container.content = None
        lista_leyendas.controls.clear()
        if total_gastos > 0:
            secciones_pie = []
            paleta = ["#14b8a6", "#f59e0b", "#3b82f6", "#a855f7", "#ec4899"]
            try:
                cats = supabase.table("categorias").select("*").eq("user_id", page.user_id).execute()
                mapa_nombres = {str(c["id"]): c["nombre"] for c in (cats.data or [])}
            except Exception:
                mapa_nombres = {}
            
            for i, (cat_id, subtotal) in enumerate(gastos_por_categoria.items()):
                cat_name = mapa_nombres.get(cat_id, cat_id).capitalize()
                color_sel = paleta[i % len(paleta)]
                porcentaje = (subtotal / total_gastos) * 100
                
                secciones_pie.append(
                    charts.PieChartSection(
                        value=float(subtotal), 
                        title=f"{porcentaje:.1f}%", 
                        color=color_sel, 
                        radius=45,
                        title_style=ft.TextStyle(size=11, color="white", weight="bold")
                    )
                )
                lista_leyendas.controls.append(
                    ft.Row([
                        ft.Container(width=10, height=10, bgcolor=color_sel, border_radius=3),
                        ft.Text(f"{cat_name}: ", size=12, color=colors["text_secondary"]),
                        ft.Text(f"${subtotal:,.2f}", size=12, color=colors["text"], weight="bold")
                    ], spacing=8)
                )
            
            grafico_container.content = charts.PieChart(
                sections=secciones_pie, 
                sections_space=2, 
                center_space_radius=35, 
                expand=True
            )
        else:
            grafico_container.content = ft.Text("No registras gastos este mes para graficar.", color=colors["text_secondary"], size=13, italic=True)
            lista_leyendas.controls.append(ft.Text("Registra gastos en la pestaña de movimientos.", size=12, color=colors["text_secondary"]))

        presupuestos_column.controls.clear()
        mensajes_alerta = []
        try:
            presupuestos_data = supabase.table("presupuestos").select("*, categorias(nombre)").eq("user_id", page.user_id).execute()
            for p in (presupuestos_data.data or []):
                cat_id_str = str(p["categoria_id"])
                nombre_cat = p.get("categorias", {}).get("nombre", "Cat").capitalize()
                limite = float(p["limite"])
                gastado = gastos_por_categoria.get(cat_id_str, 0.0)
                porcentaje_uso = (gastado / limite * 100) if limite > 0 else 0
                color_barra = ft.Colors.GREEN_400 if porcentaje_uso < 80 else ft.Colors.ORANGE_400 if porcentaje_uso < 100 else ft.Colors.RED_400
                
                presupuestos_column.controls.append(
                    ft.Column([
                        ft.Row([
                            ft.Text(f"{nombre_cat}", size=12, color=colors["text_secondary"]),
                            ft.Text(f"${gastado:.0f}/{limite:.0f}", size=12, color=colors["text"], weight="bold")
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.ProgressBar(value=min(porcentaje_uso/100, 1.0), color=color_barra, bgcolor=colors["bg"], height=6),
                    ], spacing=2)
                )
                
                if porcentaje_uso >= 100:
                    mensajes_alerta.append(f"⚠️ Límite superado en {nombre_cat}: ${gastado:.0f} de ${limite:.0f}")
                elif porcentaje_uso >= 80:
                    mensajes_alerta.append(f"⚡ Te acercas al límite en {nombre_cat}: {porcentaje_uso:.0f}%")
        except Exception:
            presupuestos_column.controls.append(ft.Text("Sin presupuestos definidos.", size=12, color=colors["text_secondary"]))

        alerta_presupuesto.visible = bool(mensajes_alerta)
        if mensajes_alerta:
            alerta_presupuesto.value = "\n".join(mensajes_alerta)

        page.update()

    async def temporizador_actualizacion():
        while True:
            await asyncio.sleep(30)
            if page.navigation_bar and page.navigation_bar.selected_index == 0:
                actualizar_dashboard()
    _timer_dashboard = asyncio.ensure_future(temporizador_actualizacion())

    columna_principal.controls.append(
        ft.Column([
            ft.Row([
                ft.Text("Resumen Financiero", size=24, weight="bold", color=colors["primary"]),
                btn_refrescar
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text("Echa un vistazo rápido al rendimiento de tu dinero.", color=colors["text_secondary"], size=14),
            ft.Row([
                ft.Icon(ft.Icons.CLOUD_SYNC, color=ft.Colors.GREEN_400, size=14),
                ft.Text("Sincronizado en todos tus dispositivos", size=12, color=ft.Colors.GREEN_400, italic=True)
            ], spacing=5),
            indicador_carga,
            alerta_presupuesto,
            ft.Divider(height=10, color="transparent"),
            row_kpis,
            ft.Divider(height=15, color="transparent"),
            ft.Text("Distribución del Gasto", size=18, weight="bold", color=colors["primary"]),
            ft.Container(
                content=ft.ResponsiveRow([
                    ft.Container(content=grafico_container, col={"xs": 12, "md": 5}),
                    ft.Container(content=lista_leyendas, col={"xs": 12, "md": 7}, padding=10, alignment=ft.Alignment.CENTER_LEFT)
                ], run_spacing=20, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15, bgcolor=colors["surface"], border_radius=16
            ),
            ft.Divider(height=15, color="transparent"),
            ft.Text("Estado de Presupuestos", size=18, weight="bold", color=colors["primary"]),
            presupuestos_column
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )
    actualizar_dashboard(True)

# ==================== PANTALLA MOVIMIENTOS (CON BANNER Y LICENCIA) ====================
def ir_a_movimientos_crud(page: ft.Page):
    global columna_principal, supabase
    cancelar_timer_dashboard()
    colors = AppColors.get(page.theme_mode)
    columna_principal.controls.clear()

    banner_limite = ft.Container(visible=False, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ORANGE), padding=10, border_radius=8)
    lista_movimientos = ft.ListView(expand=True, spacing=10, padding=5)
    mapa_categorias = {}

    def cargar_mapa_categorias():
        nonlocal mapa_categorias
        try:
            res = supabase.table("categorias").select("*").eq("user_id", page.user_id).execute()
            mapa_categorias = {str(c["id"]): c["nombre"] for c in res.data}
        except Exception:
            mapa_categorias = {}

    def obtener_nombre_categoria(registro):
        if registro.get("tipo") == "ingreso":
            return registro.get("categoria_nombre_ingreso") or "Ingreso"
        else:
            cat_id = str(registro.get("categoria_id"))
            return mapa_categorias.get(cat_id, "General")

    def refrescar_lista():
        lista_movimientos.controls.clear()
        try:
            data = supabase.table("gastos").select("*")\
                       .eq("user_id", page.user_id)\
                       .order("created_at", desc=True)\
                       .execute()
            movimientos = data.data or []
        except Exception:
            movimientos = []
            mostrar_snackbar(page, "Error al cargar movimientos.", colors["error"])

        if not movimientos:
            lista_movimientos.controls.append(
                ft.Text("No hay movimientos registrados aún.", color=colors["text_secondary"], italic=True)
            )
        else:
            for m in movimientos:
                fecha_str = m.get("created_at", "")[:10]
                concepto = m.get("nombre", "Sin concepto")
                monto = float(m.get("monto", 0) or 0)
                tipo = m.get("tipo", "gasto")
                cat_nombre = obtener_nombre_categoria(m)
                signo = "+" if tipo == "ingreso" else "-"
                color_monto = ft.Colors.GREEN_400 if tipo == "ingreso" else ft.Colors.RED_400

                lista_movimientos.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(f"{signo}${monto:,.2f}", size=16, weight="bold", color=color_monto),
                                ft.Text(f"{concepto}  •  {cat_nombre}", size=12, color=colors["text_secondary"]),
                            ], expand=True),
                            ft.Text(fecha_str, size=12, color=colors["text_secondary"]),
                            ft.IconButton(icon=ft.Icons.EDIT, icon_color=colors["primary"], tooltip="Editar", on_click=lambda e, reg=m: safe_call(editar_transaccion, reg)()),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color=colors["error"], tooltip="Eliminar", on_click=lambda e, reg=m: safe_call(confirmar_eliminar, reg)()),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=colors["surface"], padding=10, border_radius=10,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE))
                    )
                )
        page.update()

    async def verificar_estado_limite():
        plan = await obtener_plan(page)
        if plan == "paid":
            ocultar_banner_limite(page, banner_limite)
            return True
        try:
            res = supabase.table("gastos").select("count", count="exact").eq("user_id", page.user_id).execute()
            total = res.count or 0
        except Exception:
            total = 0

        if total >= 50:
            mostrar_banner_limite(page, banner_limite, "Has alcanzado el límite gratuito. Activa tu licencia para continuar.")
            return False
        else:
            ocultar_banner_limite(page, banner_limite)
            return True

    def abrir_formulario(registro_editar=None):
        if registro_editar is None:
            async def _check_and_open():
                puede = await verificar_estado_limite()
                if not puede:
                    mostrar_snackbar(page, "Límite gratuito alcanzado. Activa tu licencia.", colors["error"])
                    return
                _abrir_formulario_real(registro_editar)
            asyncio.ensure_future(_check_and_open())
        else:
            _abrir_formulario_real(registro_editar)

    def _abrir_formulario_real(registro_editar):
        nonlocal mapa_categorias
        cargar_mapa_categorias()
        form_tipo = "gasto" if registro_editar is None else registro_editar.get("tipo", "gasto")
        
        txt_concepto = ft.TextField(label="Concepto" if form_tipo == "gasto" else "Origen del ingreso",
                                    value=registro_editar.get("nombre", "") if registro_editar else "",
                                    border_color=colors["primary"], autofocus=True)
        txt_monto = ft.TextField(label="Monto ($)",
                                 value=str(registro_editar.get("monto", "")) if registro_editar else "",
                                 keyboard_type=ft.KeyboardType.NUMBER, border_color=colors["primary"])
        dd_categoria = ft.Dropdown(label="Categoría", border_color=colors["primary"], options=[])
        toggle_tipo = ft.SegmentedButton(
            allow_multiple_selection=False, selected=[form_tipo],
            segments=[ft.Segment(value="gasto", label=ft.Text("Gasto")),
                      ft.Segment(value="ingreso", label=ft.Text("Ingreso"))],
            visible=registro_editar is None
        )
        
        def cargar_opciones_categoria(según_tipo):
            nonlocal mapa_categorias
            if según_tipo == "ingreso":
                dd_categoria.options = [
                    ft.dropdown.Option(text="Capital Inicial", key="capital_inicial"),
                    ft.dropdown.Option(text="Sueldo / Nómina", key="sueldo"),
                    ft.dropdown.Option(text="Ventas / Negocio", key="ventas"),
                    ft.dropdown.Option(text="Inversiones", key="inversiones"),
                    ft.dropdown.Option(text="Otros Ingresos", key="otros_ingresos")
                ]
                dd_categoria.value = "capital_inicial"
            else:
                try:
                    res = supabase.table("categorias").select("*").eq("user_id", page.user_id).execute()
                    opciones = [ft.dropdown.Option(text=c["nombre"].capitalize(), key=str(c["id"])) for c in res.data]
                    if not opciones:
                        opciones.append(ft.dropdown.Option(text="General", key="1"))
                    dd_categoria.options = opciones
                    dd_categoria.value = opciones[0].key
                except Exception:
                    dd_categoria.options = [ft.dropdown.Option(text="General", key="1")]
                    dd_categoria.value = "1"

        cargar_opciones_categoria(form_tipo)
        if registro_editar:
            dd_categoria.value = str(registro_editar.get("categoria_id", "")) if form_tipo == "gasto" else registro_editar.get("categoria_nombre_ingreso", "")

        def on_tipo_change(e):
            nuevo_tipo = next(iter(e.control.selected))
            nonlocal form_tipo
            form_tipo = nuevo_tipo
            cargar_opciones_categoria(nuevo_tipo)
            txt_concepto.label = "Concepto" if nuevo_tipo == "gasto" else "Origen del ingreso"
            page.update()

        toggle_tipo.on_change = on_tipo_change

        def guardar_click(e):
            concepto = txt_concepto.value.strip()
            monto_str = txt_monto.value.strip()
            if not concepto:
                mostrar_snackbar(page, "El concepto es obligatorio.", colors["error"])
                return
            try:
                monto_num = float(monto_str)
                if monto_num <= 0:
                    mostrar_snackbar(page, "El monto debe ser mayor a cero.", colors["error"])
                    return
            except ValueError:
                mostrar_snackbar(page, "Ingresa un monto numérico válido.", colors["error"])
                return

            datos = {"monto": monto_num, "nombre": concepto, "tipo": form_tipo, "user_id": page.user_id}
            if form_tipo == "gasto":
                datos["categoria_id"] = int(dd_categoria.value) if dd_categoria.value.isdigit() else None
            else:
                datos["categoria_nombre_ingreso"] = dd_categoria.value

            async def _guardar():
                try:
                    if registro_editar:
                        supabase.table("gastos").update(datos).eq("id", registro_editar["id"]).execute()
                        mostrar_snackbar(page, "Movimiento actualizado con éxito.", colors["success"])
                    else:
                        supabase.table("gastos").insert(datos).execute()
                        mostrar_snackbar(page, "Movimiento creado correctamente.", colors["success"])
                    bs.open = False
                    page.update()
                    refrescar_lista()
                    global _cache_dashboard
                    _cache_dashboard["timestamp"] = 0
                except Exception as ex:
                    if "row-level security" in str(ex).lower() or "permission denied" in str(ex).lower():
                        mostrar_snackbar(page, "Límite gratuito alcanzado. Activa tu licencia.", colors["error"])
                        asyncio.ensure_future(verificar_estado_limite())
                    else:
                        mostrar_snackbar(page, f"Error al guardar: {ex}", colors["error"])

            asyncio.ensure_future(_guardar())

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Editar Movimiento" if registro_editar else "Nuevo Movimiento", size=20, weight="bold"),
                    toggle_tipo, txt_concepto, dd_categoria, txt_monto,
                    ft.FilledButton("Guardar", on_click=lambda e: safe_call(guardar_click, e)()),
                ], spacing=15, tight=True),
                padding=20, bgcolor=colors["surface"],
                border_radius=ft.BorderRadius(top_left=16, top_right=16, bottom_left=0, bottom_right=0)
            ),
            open=True,
        )
        page.overlay.append(bs)
        page.update()

    def editar_transaccion(registro):
        abrir_formulario(registro_editar=registro)

    def confirmar_eliminar(registro):
        def eliminar_click(e):
            try:
                supabase.table("gastos").delete().eq("id", registro["id"]).execute()
                mostrar_snackbar(page, "Movimiento eliminado.", colors["success"])
                dlg.open = False
                page.update()
                refrescar_lista()
                global _cache_dashboard
                _cache_dashboard["timestamp"] = 0
            except Exception as ex:
                mostrar_snackbar(page, f"Error al eliminar: {ex}", colors["error"])

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar eliminación"),
            content=ft.Text(f"¿Eliminar '{registro.get('nombre', 'sin nombre')}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page)),
                ft.TextButton("Eliminar", on_click=lambda e: safe_call(eliminar_click, e)()),
            ],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    columna_principal.controls.append(
        ft.Column([
            ft.Row([
                ft.Text("Tus Movimientos", size=24, weight="bold", color=colors["primary"]),
                ft.FloatingActionButton(icon=ft.Icons.ADD, bgcolor=colors["primary"], on_click=lambda e: safe_call(abrir_formulario)())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            banner_limite,
            ft.Divider(height=10, color="transparent"),
            lista_movimientos
        ], expand=True, scroll=ft.ScrollMode.AUTO)
    )
    cargar_mapa_categorias()
    refrescar_lista()
    asyncio.ensure_future(verificar_estado_limite())
    page.update()

# ==================== PRESUPUESTOS ====================
def ir_a_presupuestos(page: ft.Page):
    global columna_principal, supabase
    cancelar_timer_dashboard()
    colors = AppColors.get(page.theme_mode)
    columna_principal.controls.clear()

    lista_presupuestos = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    
    def refrescar_presupuestos():
        lista_presupuestos.controls.clear()
        try:
            cats = supabase.table("categorias").select("*").eq("user_id", page.user_id).execute()
            pres = supabase.table("presupuestos").select("*").eq("user_id", page.user_id).execute()
            limites = {str(p["categoria_id"]): p for p in (pres.data or [])}
            
            for cat in (cats.data or []):
                cat_id = str(cat["id"])
                nombre = cat["nombre"].capitalize()
                limite_actual = limites.get(cat_id, {}).get("limite", 0.0)
                pres_id = limites.get(cat_id, {}).get("id")
                
                txt_limite = ft.TextField(value=str(limite_actual) if limite_actual else "",
                                          keyboard_type=ft.KeyboardType.NUMBER, width=100, text_align=ft.TextAlign.END,
                                          border_color=colors["primary"])
                
                def guardar_limite(e, cid=cat_id, pid=pres_id, txt=txt_limite):
                    try:
                        nuevo_limite = float(txt.value.strip()) if txt.value.strip() else 0.0
                    except ValueError:
                        mostrar_snackbar(page, "Ingresa un número válido.", colors["error"])
                        return
                    try:
                        if pid:
                            supabase.table("presupuestos").update({"limite": nuevo_limite}).eq("id", pid).execute()
                        else:
                            supabase.table("presupuestos").insert({"categoria_id": int(cid), "limite": nuevo_limite, "user_id": page.user_id}).execute()
                        mostrar_snackbar(page, f"Presupuesto de {nombre} actualizado.", colors["success"])
                        refrescar_presupuestos()
                        global _cache_dashboard
                        _cache_dashboard["timestamp"] = 0
                    except Exception as ex:
                        mostrar_snackbar(page, f"Error: {ex}", colors["error"])
                
                lista_presupuestos.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text(nombre, size=14, weight="bold", color=colors["text"], expand=True),
                            ft.Text("$", size=14, color=colors["text_secondary"]),
                            txt_limite,
                            ft.IconButton(icon=ft.Icons.SAVE, icon_color=colors["primary"], tooltip="Guardar",
                                          on_click=lambda e, cid=cat_id, pid=pres_id, txt=txt_limite: safe_call(guardar_limite, None, cid, pid, txt)())
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        bgcolor=colors["surface"], padding=10, border_radius=8
                    )
                )
        except Exception as ex:
            lista_presupuestos.controls.append(ft.Text(f"Error: {ex}", color=colors["error"]))
        page.update()
    
    columna_principal.controls.append(
        ft.Column([
            ft.Row([ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=colors["primary"], on_click=lambda e: safe_call(ejecutar_vista_dashboard, page)()),
                    ft.Text("Presupuestos Mensuales", size=24, weight="bold", color=colors["primary"])],
                   alignment=ft.MainAxisAlignment.START),
            ft.Text("Define límites por categoría para controlar tus gastos.", color=colors["text_secondary"]),
            ft.Divider(height=10, color="transparent"),
            lista_presupuestos
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )
    refrescar_presupuestos()

# ==================== PERFIL DE USUARIO ====================
def ir_a_perfil(page: ft.Page):
    global columna_principal, supabase
    cancelar_timer_dashboard()
    colors = AppColors.get(page.theme_mode)
    columna_principal.controls.clear()
    
    try:
        user = supabase.auth.get_user()
        email = user.user.email if user and user.user else "No disponible"
    except Exception:
        email = "Error al obtener usuario"
    
    total_movimientos = 0
    try:
        res = supabase.table("gastos").select("count", count="exact").eq("user_id", page.user_id).execute()
        total_movimientos = res.count or 0
    except Exception:
        pass

    lbl_plan = ft.Text("Plan: ...", size=12, color=colors["text_secondary"])
    
    async def cargar_plan_perfil():
        plan = await obtener_plan(page)
        lbl_plan.value = f"Plan: {'Premium' if plan == 'paid' else 'Gratuito'}"
        page.update()
    
    asyncio.ensure_future(cargar_plan_perfil())

    txt_pin_nuevo = ft.TextField(label="Nuevo PIN (4 dígitos)", password=True,
                                 keyboard_type=ft.KeyboardType.NUMBER, max_length=4,
                                 border_color=colors["primary"], color=colors["text"])
    
    def cambiar_pin(e):
        nuevo = txt_pin_nuevo.value.strip()
        if len(nuevo) != 4:
            mostrar_snackbar(page, "El PIN debe tener 4 dígitos.", colors["error"])
            return
        save_pin_hash(nuevo)
        mostrar_snackbar(page, "PIN actualizado correctamente.", colors["success"])
        txt_pin_nuevo.value = ""
        page.update()

    columna_principal.controls.append(
        ft.Column([
            ft.Row([ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=colors["primary"], on_click=lambda e: safe_call(ejecutar_vista_dashboard, page)()),
                    ft.Text("Perfil", size=24, weight="bold", color=colors["primary"])],
                   alignment=ft.MainAxisAlignment.START),
            ft.Divider(height=20, color="transparent"),
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=60, color=colors["primary"]),
                    ft.Text(email, size=14, color=colors["text"], weight="bold"),
                    ft.Text(f"Total de movimientos: {total_movimientos}", size=12, color=colors["text_secondary"]),
                    ft.Row([
                        ft.Icon(ft.Icons.CLOUD_SYNC, color=ft.Colors.GREEN_400, size=12),
                        ft.Text("Sincronizado en todos tus dispositivos", size=11, color=ft.Colors.GREEN_400, italic=True)
                    ], spacing=3),
                    lbl_plan,
                    ft.Text("© 2026 Armando Hernández Vega. Todos los derechos reservados.", size=10, color=colors["text_secondary"], italic=True),
                    ft.Text("Soporte: ahernandezvega907@gmail.com]", size=10, color=colors["text_secondary"]),
                    ft.TextButton("Activar Licencia", on_click=lambda e: safe_call(mostrar_dialogo_activacion, page)())
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20, bgcolor=colors["surface"], border_radius=16
            ),
            ft.Divider(height=20, color="transparent"),
            ft.Text("Cambiar PIN", size=18, weight="bold", color=colors["primary"]),
            ft.Text("Por seguridad, usa 4 dígitos.", size=12, color=colors["text_secondary"]),
            ft.Row([txt_pin_nuevo, ft.FilledButton("Actualizar", on_click=lambda e: safe_call(cambiar_pin, e)())],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=20, color="transparent"),
            ft.FilledButton("Cerrar Sesión", on_click=lambda e: safe_call(cerrar_sesion_action, page)(),
                            style=ft.ButtonStyle(bgcolor=colors["error"], color="white"))
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )
    page.update()

# ==================== ESTADÍSTICAS Y EXPORTACIÓN ====================
def ejecutar_vista_estadisticas_segura(page_ref: ft.Page):
    cancelar_timer_dashboard()
    colors = AppColors.get(page_ref.theme_mode)
    grafico_container = ft.Container(height=220)          # pastel
    barras_container = ft.Container(height=220)           # barras
    lista_leyendas = ft.Column(spacing=8)
    historial_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    txt_total_analizado = ft.Text("Total analizado: $0.00", color="grey")
    gastos_locales = []

    # ---------- Botones de exportación (corregidos) ----------
    btn_csv = ft.FilledButton(
        content=ft.Text("Exportar CSV"),
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        style=ft.ButtonStyle(bgcolor=colors["surface"]),
        on_click=lambda e: safe_call(exportar_a_csv, e)
    )
    btn_excel = ft.FilledButton(
        content=ft.Text("Exportar Excel"),
        icon=ft.Icons.TABLE_CHART,
        style=ft.ButtonStyle(bgcolor=colors["surface"]),
        visible=False,
        on_click=lambda e: safe_call(exportar_a_excel, e)
    )
    btn_pdf = ft.FilledButton(
        content=ft.Text("Exportar PDF"),
        icon=ft.Icons.PICTURE_AS_PDF,
        style=ft.ButtonStyle(bgcolor=colors["surface"]),
        visible=False,
        on_click=lambda e: safe_call(exportar_a_pdf, e)
    )

    async def configurar_botones_exportacion():
        plan = await obtener_plan(page_ref)
        es_premium = (plan == "paid")
        btn_excel.visible = es_premium
        btn_pdf.visible = es_premium
        page_ref.update()

    asyncio.ensure_future(configurar_botones_exportacion())

    # ---------- Funciones de exportación ----------
    def exportar_a_csv(e):
        if not gastos_locales:
            mostrar_snackbar(page_ref, "No hay datos disponibles para exportar.", colors["error"])
            return
        try:
            nombre_archivo = "moneyflow_gastos.csv"
            with open(nombre_archivo, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Fecha", "Concepto", "Categoria", "Monto ($)"])
                for g in gastos_locales:
                    writer.writerow([
                        g.get("created_at") or "N/A",
                        g.get("nombre", "Gasto"),
                        g.get("categoria_id") or "General",
                        f"{float(g.get('monto', 0)):.2f}"
                    ])
            mostrar_snackbar(page_ref, f"📥 CSV exportado con éxito a {nombre_archivo}!", colors["success"])
        except Exception as ex:
            mostrar_snackbar(page_ref, f"Error al exportar CSV: {ex}", colors["error"])

    def exportar_a_excel(e):
        if not gastos_locales:
            mostrar_snackbar(page_ref, "No hay datos disponibles para exportar.", colors["error"])
            return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Gastos"
            ws.append(["Fecha", "Concepto", "Categoria", "Monto ($)"])
            for g in gastos_locales:
                ws.append([
                    g.get("created_at") or "N/A",
                    g.get("nombre", "Gasto"),
                    g.get("categoria_id") or "General",
                    float(g.get("monto", 0))
                ])
            nombre_archivo = "moneyflow_gastos.xlsx"
            wb.save(nombre_archivo)
            mostrar_snackbar(page_ref, f"📥 Excel exportado con éxito a {nombre_archivo}!", colors["success"])
        except ImportError:
            mostrar_snackbar(page_ref, "Librería openpyxl no instalada. Contacte al soporte.", colors["error"])
        except Exception as ex:
            mostrar_snackbar(page_ref, f"Error al exportar Excel: {ex}", colors["error"])

    def exportar_a_pdf(e):
        if not gastos_locales:
            mostrar_snackbar(page_ref, "No hay datos disponibles para exportar.", colors["error"])
            return
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            nombre_archivo = "moneyflow_gastos.pdf"
            c = canvas.Canvas(nombre_archivo, pagesize=letter)
            width, height = letter
            y = height - 50
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, "Reporte de Gastos - MoneyFlow")
            y -= 30
            c.setFont("Helvetica", 10)
            for g in gastos_locales:
                linea = f"{g.get('created_at','N/A')} | {g.get('nombre','Gasto')} | {g.get('categoria_id','General')} | ${float(g.get('monto',0)):.2f}"
                c.drawString(50, y, linea)
                y -= 15
                if y < 50:
                    c.showPage()
                    y = height - 50
            c.save()
            mostrar_snackbar(page_ref, f"📥 PDF exportado con éxito a {nombre_archivo}!", colors["success"])
        except ImportError:
            mostrar_snackbar(page_ref, "Librería reportlab no instalada. Contacte al soporte.", colors["error"])
        except Exception as ex:
            mostrar_snackbar(page_ref, f"Error al exportar PDF: {ex}", colors["error"])

    def aplicar_filtro_y_renderizar(filtro_seleccionado):
        nonlocal gastos_locales
        grafico_container.content = None
        barras_container.content = None
        lista_leyendas.controls.clear()
        historial_column.controls.clear()
        total_acumulado = 0.0
        ahora = datetime.now()
        gastos_filtrados = []

        for g in gastos_locales:
            if g is None: continue
            fecha_str = g.get("created_at") or g.get("fecha") or ""
            try: fecha_gasto = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            except Exception: fecha_gasto = ahora

            if filtro_seleccionado == "hoy":
                if fecha_gasto.date() == ahora.date(): gastos_filtrados.append(g)
            elif filtro_seleccionado == "mes":
                if fecha_gasto.year == ahora.year and fecha_gasto.month == ahora.month: gastos_filtrados.append(g)
            else:
                gastos_filtrados.append(g)

        # Pastel
        if gastos_filtrados:
            totales_por_categoria = {}
            for g in gastos_filtrados:
                monto_gasto = float(g.get("monto", 0) or 0)
                if g.get("tipo") != "ingreso":
                    total_acumulado += monto_gasto
                    cat = str(g.get("categoria_id") or g.get("categoria") or "Otros").capitalize()
                    totales_por_categoria[cat] = totales_por_categoria.get(cat, 0.0) + monto_gasto

                historial_column.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.FASTFOOD if "comid" in cat.lower() else ft.Icons.ATTACH_MONEY, color=colors["primary"]),
                            ft.Column([ft.Text(g.get("nombre", "Gasto"), weight="bold"), ft.Text(cat, size=12, color="grey")], expand=True),
                            ft.Text(f"-${monto_gasto:.2f}", color="red", weight="bold")
                        ]),
                        padding=10, border=ft.Border.all(1, "grey800"), border_radius=8
                    )
                )

            secciones_pie = []
            paleta = [ft.Colors.TEAL, ft.Colors.ORANGE, ft.Colors.BLUE, ft.Colors.PURPLE]
            for i, (cat_name, total_cat) in enumerate(totales_por_categoria.items()):
                color_sel = paleta[i % len(paleta)]
                porcentaje = (total_cat / total_acumulado) * 100 if total_acumulado > 0 else 0
                secciones_pie.append(charts.PieChartSection(value=float(total_cat), title=f"{porcentaje:.1f}%", color=color_sel, radius=40))
                lista_leyendas.controls.append(ft.Row([ft.Container(width=12, height=12, bgcolor=color_sel, border_radius=3), ft.Text(f"{cat_name}: ${total_cat:.2f}")]))
            
            grafico_container.content = charts.PieChart(sections=secciones_pie, sections_space=2, center_space_radius=40, expand=True)
        else:
            grafico_container.content = ft.Row([ft.Text("No hay transacciones en este período.", color="grey")], alignment=ft.MainAxisAlignment.CENTER)

        # Barras
        ingresos_periodo = {}
        gastos_periodo = {}
        for g in gastos_filtrados:
            fecha_str = g.get("created_at") or ""
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            except:
                continue
            if filtro_seleccionado == "hoy":
                clave = "Hoy"
            elif filtro_seleccionado == "mes":
                clave = fecha.strftime("%d")
            else:
                clave = fecha.strftime("%Y-%m")

            monto = float(g.get("monto", 0) or 0)
            if g.get("tipo") == "ingreso":
                ingresos_periodo[clave] = ingresos_periodo.get(clave, 0.0) + monto
            else:
                gastos_periodo[clave] = gastos_periodo.get(clave, 0.0) + monto

        if filtro_seleccionado == "hoy":
            grupos = ["Hoy"]
        elif filtro_seleccionado == "mes":
            import calendar
            dias_mes = calendar.monthrange(ahora.year, ahora.month)[1]
            grupos = [str(d) for d in range(1, dias_mes+1)]
        else:
            grupos = sorted(set(list(ingresos_periodo.keys()) + list(gastos_periodo.keys())))

        barras_ingresos = [ingresos_periodo.get(g, 0.0) for g in grupos]
        barras_gastos = [gastos_periodo.get(g, 0.0) for g in grupos]

        if any(barras_ingresos) or any(barras_gastos):
            bar_chart = charts.BarChart(
                bar_groups=[
                    charts.BarChartGroup(
                        x=i,
                        bar_rods=[
                            charts.BarChartRod(data=ingresos_periodo.get(g, 0.0), color=ft.Colors.GREEN_400, tooltip=f"Ingresos: ${ingresos_periodo.get(g, 0.0):.2f}"),
                            charts.BarChartRod(data=gastos_periodo.get(g, 0.0), color=ft.Colors.RED_400, tooltip=f"Gastos: ${gastos_periodo.get(g, 0.0):.2f}"),
                        ]
                    )
                    for i, g in enumerate(grupos)
                ],
                bottom_axis=charts.ChartAxis(labels=[charts.ChartAxisLabel(value=i, label=ft.Text(g, size=8)) for i, g in enumerate(grupos)]),
                left_axis=charts.ChartAxis(labels_size=40),
                tooltip_bgcolor=ft.Colors.with_opacity(0.8, ft.Colors.BLACK),
                max_y=max(max(barras_ingresos), max(barras_gastos)) * 1.1 if max(barras_ingresos + barras_gastos) > 0 else 10,
                expand=True,
            )
            barras_container.content = bar_chart
        else:
            barras_container.content = ft.Row([ft.Text("Sin datos para el gráfico de barras.", color="grey")], alignment=ft.MainAxisAlignment.CENTER)

        txt_total_analizado.value = f"Total analizado: ${total_acumulado:.2f}"
        page_ref.update()

    try:
        raw_gastos = supabase.table("gastos").select("*").eq("user_id", page_ref.user_id).execute()
        gastos_locales = raw_gastos.data or []
    except Exception:
        grafico_container.content = ft.Text("Error de red al actualizar datos desde la nube.", color="red")

    selector_tiempo = ft.SegmentedButton(
        allow_multiple_selection=False, selected=["mes"],
        on_change=lambda e: safe_call(aplicar_filtro_y_renderizar, next(iter(e.control.selected)) if e.control.selected else "mes")(),
        segments=[ft.Segment(value="hoy", label=ft.Text("Hoy"), icon=ft.Icon(ft.Icons.CALENDAR_TODAY)),
                  ft.Segment(value="mes", label=ft.Text("Este Mes"), icon=ft.Icon(ft.Icons.CALENDAR_MONTH)),
                  ft.Segment(value="todo", label=ft.Text("Todo"), icon=ft.Icon(ft.Icons.ALL_INCLUSIVE))]
    )

    bloque_grafico_adaptable = ft.ResponsiveRow([
        ft.Container(content=grafico_container, col={"xs": 12, "md": 5}),
        ft.Container(content=lista_leyendas, col={"xs": 12, "md": 7}, padding=10)
    ], run_spacing=20)

    columna_principal.controls.clear()
    columna_principal.controls.append(
        ft.Column([
            ft.Row([
                ft.Text("Métricas Avanzadas", size=24, weight="bold", color=colors["primary"]),
                ft.Row([btn_csv, btn_excel, btn_pdf], spacing=5)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([selector_tiempo], alignment=ft.MainAxisAlignment.CENTER),
            txt_total_analizado,
            ft.Divider(height=10, color="transparent"),
            bloque_grafico_adaptable,
            ft.Divider(height=20, color="transparent"),
            ft.Text("Tendencia de Ingresos y Gastos", size=18, weight="bold", color=colors["primary"]),
            barras_container,
            ft.Divider(height=20, color="transparent"),
            ft.Text("Historial", size=18, weight="bold", color=colors["primary"]),
            historial_column
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )
    aplicar_filtro_y_renderizar("mes")

# ==================== CATEGORÍAS ====================
def ir_a_configuracion_categorias(page: ft.Page):
    global columna_principal, supabase
    cancelar_timer_dashboard()
    colors = AppColors.get(page.theme_mode)
    columna_principal.controls.clear()

    txt_nueva_cat = ft.TextField(label="Nueva categoría", hint_text="Ej. Entretenimiento, Educación...",
                                 border_color=colors["primary"], expand=True)
    lista_categorias_vista = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar_lista_categorias():
        lista_categorias_vista.controls.clear()
        try:
            res = supabase.table("categorias").select("*").eq("user_id", page.user_id).order("nombre").execute()
            categorias = res.data or []
        except Exception:
            mostrar_snackbar(page, "Error al cargar categorías.", colors["error"])
            categorias = []

        if not categorias:
            lista_categorias_vista.controls.append(
                ft.Text("No tienes categorías. Crea una nueva.", color=colors["text_secondary"], italic=True)
            )
        else:
            for cat in categorias:
                cat_id = cat["id"]
                nombre = str(cat.get("nombre", "")).capitalize()
                try:
                    count_res = supabase.table("gastos").select("count", count="exact").eq("categoria_id", cat_id).eq("user_id", page.user_id).execute()
                    count = count_res.count if count_res.count else 0
                except:
                    count = 0

                lista_categorias_vista.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.LABEL_OUTLINE, color=colors["primary"], size=20),
                            ft.Column([
                                ft.Text(nombre, weight="bold", color=colors["text"], size=14),
                                ft.Text(f"{count} gastos", size=11, color=colors["text_secondary"])
                            ], expand=True),
                            ft.IconButton(icon=ft.Icons.EDIT, icon_color=colors["primary"], tooltip="Editar",
                                          on_click=lambda e, c=cat: editar_categoria(c)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color=colors["error"], tooltip="Eliminar",
                                          on_click=lambda e, c=cat: confirmar_eliminar_categoria(c)),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=10, bgcolor=colors["surface"], border_radius=8,
                        margin=ft.margin.only(bottom=5)
                    )
                )
        page.update()

    def guardar_categoria_click(e):
        nombre = txt_nueva_cat.value.strip()
        if not nombre:
            mostrar_snackbar(page, "Escribe un nombre.", colors["error"])
            return
        try:
            supabase.table("categorias").insert({"nombre": nombre, "user_id": page.user_id}).execute()
            mostrar_snackbar(page, f"¡Categoría '{nombre}' creada!", colors["success"])
            txt_nueva_cat.value = ""
            refrescar_lista_categorias()
            global _cache_dashboard
            _cache_dashboard["timestamp"] = 0
        except Exception as e:
            mostrar_snackbar(page, f"Error al guardar: {e}", colors["error"])

    def editar_categoria(cat):
        nombre_actual = cat.get("nombre", "")
        txt_editar = ft.TextField(value=nombre_actual, label="Nuevo nombre", border_color=colors["primary"], autofocus=True)
        
        def guardar_edicion(e):
            nuevo_nombre = txt_editar.value.strip()
            if not nuevo_nombre:
                mostrar_snackbar(page, "El nombre no puede estar vacío.", colors["error"])
                return
            try:
                supabase.table("categorias").update({"nombre": nuevo_nombre}).eq("id", cat["id"]).execute()
                mostrar_snackbar(page, "Categoría actualizada.", colors["success"])
                dlg_edit.open = False
                page.update()
                refrescar_lista_categorias()
                _cache_dashboard["timestamp"] = 0
            except Exception as ex:
                mostrar_snackbar(page, f"Error: {ex}", colors["error"])

        dlg_edit = ft.AlertDialog(
            title=ft.Text("Editar categoría"),
            content=ft.Column([txt_editar]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page)),
                ft.FilledButton("Guardar", on_click=lambda e: safe_call(guardar_edicion, e)()),
            ],
        )
        page.dialog = dlg_edit
        dlg_edit.open = True
        page.update()

    def confirmar_eliminar_categoria(cat):
        try:
            count_res = supabase.table("gastos").select("count", count="exact").eq("categoria_id", cat["id"]).eq("user_id", page.user_id).execute()
            count = count_res.count if count_res.count else 0
        except:
            count = 0

        mensaje = f"¿Eliminar la categoría '{cat.get('nombre', '')}'?"
        if count > 0:
            mensaje += f"\n\nTiene {count} gastos asociados. Quedarán sin categoría (General)."

        def eliminar_click(e):
            try:
                if count > 0:
                    supabase.table("gastos").update({"categoria_id": None}).eq("categoria_id", cat["id"]).eq("user_id", page.user_id).execute()
                supabase.table("categorias").delete().eq("id", cat["id"]).execute()
                mostrar_snackbar(page, "Categoría eliminada.", colors["success"])
                dlg_confirm.open = False
                page.update()
                refrescar_lista_categorias()
                _cache_dashboard["timestamp"] = 0
            except Exception as ex:
                mostrar_snackbar(page, f"Error al eliminar: {ex}", colors["error"])

        dlg_confirm = ft.AlertDialog(
            title=ft.Text("Eliminar categoría"),
            content=ft.Text(mensaje, size=14),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page)),
                ft.FilledButton("Eliminar", on_click=lambda e: safe_call(eliminar_click, e)(),
                                style=ft.ButtonStyle(bgcolor=colors["error"], color="white")),
            ],
        )
        page.dialog = dlg_confirm
        dlg_confirm.open = True
        page.update()

    columna_principal.controls.append(
        ft.Column([
            ft.Row([ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=colors["primary"],
                                  on_click=lambda e: safe_call(ejecutar_vista_dashboard, page)()),
                    ft.Text("Gestión de Categorías", size=24, weight="bold", color=colors["primary"])],
                   alignment=ft.MainAxisAlignment.START),
            ft.Text("Crea, edita o elimina categorías para organizar tus gastos.", color=colors["text_secondary"]),
            ft.Divider(height=10, color="transparent"),
            ft.Row([txt_nueva_cat, ft.IconButton(icon=ft.Icons.ADD_CIRCLE, icon_color=colors["success"], icon_size=40,
                                                  on_click=lambda e: safe_call(guardar_categoria_click, e)())],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=10, color="transparent"),
            lista_categorias_vista
        ], scroll=ft.ScrollMode.AUTO, expand=True)
    )
    page.update()
    refrescar_lista_categorias()

# ==================== ASISTENTE: CHAT INTERACTIVO GURÚ IA ====================
async def obtener_contexto_financiero(page: ft.Page) -> str:
    """Recopila datos reales del usuario para personalizar la respuesta de la IA."""
    try:
        res = supabase.table("gastos").select("*").eq("user_id", page.user_id).execute()
        movimientos = res.data or []
    except Exception:
        return "No se pudieron obtener los datos financieros."

    ahora = datetime.now()
    gastos_mes = 0.0
    ingresos_mes = 0.0
    categorias = {}
    ultimos = []

    for m in movimientos:
        try:
            fecha = datetime.fromisoformat(m.get("created_at", "").replace("Z", "+00:00"))
        except:
            continue
        if fecha.year == ahora.year and fecha.month == ahora.month:
            monto = float(m.get("monto", 0) or 0)
            if m.get("tipo") == "ingreso":
                ingresos_mes += monto
            else:
                gastos_mes += monto
                cat = str(m.get("categoria_id") or "General")
                categorias[cat] = categorias.get(cat, 0.0) + monto
        # Últimos 5 movimientos
        if len(ultimos) < 5:
            ultimos.append(f"{m.get('nombre','')}: ${m.get('monto',0)} ({m.get('tipo','gasto')})")

    balance = ingresos_mes - gastos_mes
    contexto = (
        f"Balance del mes: ${balance:.2f} (Ingresos: ${ingresos_mes:.2f}, Gastos: ${gastos_mes:.2f}).\n"
        f"Categorías con más gasto: {categorias if categorias else 'ninguna'}.\n"
        f"Últimos movimientos: {', '.join(ultimos) if ultimos else 'ninguno'}.\n"
    )
    return contexto


def abrir_chat_guru(page: ft.Page):
    colors = AppColors.get(page.theme_mode)
    txt_pregunta = ft.TextField(
        label="Pregúntale algo al Gurú...",
        hint_text="Ej. ¿Cómo puedo ahorrar el 20%?",
        expand=True,
        border_color=colors["primary"],
        color=colors["text"],
        text_size=14,
    )
    contenedor_respuesta = ft.Column([
        ft.Text(
            "💡 Consejos rápidos:\nRecuerda mantener tus gastos fijos por debajo del 50%...",
            size=14,
            color=colors["text_secondary"],
            italic=True,
        )
    ], spacing=10)

    async def verificar_acceso_guru() -> tuple[bool, str]:
        """
        Retorna (permitido, mensaje_error).
        Si es Premium, siempre permitido.
        Si es Gratuito, solo permitido si tiene menos de 50 movimientos.
        """
        try:
            plan = await obtener_plan(page)
        except:
            plan = "free"

        if plan == "paid":
            return True, ""

        # Plan gratuito: verificar conteo de movimientos
        try:
            res = supabase.table("gastos").select("count", count="exact").eq("user_id", page.user_id).execute()
            total = res.count or 0
        except:
            total = 0

        if total >= 50:
            return False, "Has alcanzado el límite gratuito. Adquiere la licencia Premium para acceder al Gurú IA ilimitado."
        return True, ""

    async def enviar_pregunta_click(e):
        pregunta = txt_pregunta.value.strip()
        if not pregunta:
            return

        # Verificar acceso
        permitido, mensaje_bloqueo = await verificar_acceso_guru()
        if not permitido:
            contenedor_respuesta.controls.clear()
            contenedor_respuesta.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("🔒 Acceso restringido", size=16, weight="bold", color=colors["error"]),
                        ft.Text(mensaje_bloqueo, size=14, color=colors["text_secondary"]),
                        ft.TextButton("Comprar Premium ($10)", on_click=lambda e: page.launch_url("https://vega907.gumroad.com/l/moneyflow-premium")),
                    ], spacing=10),
                    padding=12,
                    bgcolor=colors["bg"],
                    border_radius=10,
                    border=ft.Border.all(1, colors["error"]),
                )
            )
            page.update()
            return

        contenedor_respuesta.controls.clear()
        contenedor_respuesta.controls.append(
            ft.Row([
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=colors["primary"]),
                ft.Text(" El Gurú está pensando...", size=13, italic=True, color=colors["text_secondary"]),
            ])
        )
        page.update()
        txt_pregunta.value = ""

        # Determinar respuesta según plan
        try:
            plan = await obtener_plan(page)
        except:
            plan = "free"

        if plan == "paid" and os.getenv("OPENAI_API_KEY"):
            try:
                contexto = await obtener_contexto_financiero(page)
                respuesta_guru = await llamar_ia_guru(pregunta, contexto)
            except Exception as ex:
                respuesta_guru = f"Error al consultar la IA: {ex}. Intentá de nuevo."
        else:
            # Respuestas predefinidas para plan gratuito (mientras no alcance límite)
            pregunta_lower = pregunta.lower()
            if "ahorrar" in pregunta_lower or "ahorro" in pregunta_lower:
                respuesta_guru = "Automatizá tu ahorro: transferí el 10% de tus ingresos a otra cuenta apenas cobres."
            elif "gasto" in pregunta_lower or "gastar" in pregunta_lower:
                respuesta_guru = "Revisá Métricas. Si Entretenimiento o Comida superan el 30% de tus ingresos, ajustá tu presupuesto."
            elif "invertir" in pregunta_lower or "inversion" in pregunta_lower:
                respuesta_guru = "Antes de invertir, tené un fondo de emergencia de 3-6 meses de gastos fijos."
            else:
                respuesta_guru = "Registrá cada ingreso y gasto en MoneyFlow para obtener un diagnóstico exacto."

        contenedor_respuesta.controls.clear()
        contenedor_respuesta.controls.append(
            ft.Column([
                ft.Text(f"👤 Tu duda: {pregunta}", size=12, color=colors["text_secondary"]),
                ft.Container(
                    content=ft.Text(f"✨ Gurú: {respuesta_guru}", size=14, color=colors["text"]),
                    bgcolor=colors["bg"],
                    padding=12,
                    border_radius=10,
                    border=ft.Border.all(1, colors["primary"]),
                ),
            ])
        )
        page.update()

    async def llamar_ia_guru(pregunta_usuario: str, contexto_financiero: str) -> str:
        """Llama a la API de OpenAI con el contexto del usuario."""
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")
        system_prompt = (
            "Sos un asesor financiero amigable y experto. Usá los datos reales del usuario "
            "para dar consejos personalizados y prácticos. Respondé siempre en español, "
            "con un tono cálido y motivador.\n\n"
            f"DATOS DEL USUARIO:\n{contexto_financiero}"
        )
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta_usuario},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    def cerrar_bs(e):
        bs.open = False
        page.update()

    bs = ft.BottomSheet(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, color="amber", size=28),
                        ft.Text(" Gurú Financiero IA", size=20, weight=ft.FontWeight.BOLD, color=colors["text"]),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Divider(color=colors["text_secondary"]),
                    contenedor_respuesta,
                    ft.Divider(height=10, color="transparent"),
                    ft.Row([
                        txt_pregunta,
                        ft.IconButton(
                            icon=ft.Icons.SEND_ROUNDED,
                            icon_color=colors["primary"],
                            icon_size=28,
                            tooltip="Enviar pregunta",
                            on_click=lambda e: safe_async(enviar_pregunta_click, e),
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=5, color="transparent"),
                    ft.FilledButton("Cerrar Chat", on_click=lambda e: safe_call(cerrar_bs, e)(), style=ft.ButtonStyle(bgcolor=colors["surface"])),
                ],
                tight=True,
                spacing=12,
            ),
            padding=20,
            bgcolor=colors["surface"],
            border_radius=ft.BorderRadius(top_left=16, top_right=16, bottom_left=0, bottom_right=0),
        ),
        open=True,
    )
    page.overlay.append(bs)
    page.update()


# ==================== CERRAR SESIÓN ====================
def cerrar_sesion_action(page: ft.Page):
    colors = AppColors.get(page.theme_mode)
    page.user_id = None
    page.navigation_bar = None
    page.appbar = None
    mostrar_snackbar(page, "🔒 Sesión cerrada de forma segura.", colors["text_secondary"])
    login_view(page)

# ==================== INTERFAZ PRINCIPAL ====================
def mostrar_interfaz_principal(page: ft.Page):
    global columna_principal
    colors = AppColors.get(page.theme_mode)
    page.controls.clear()
    
    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.MONEY_OFF_OUTLINED, color=colors["primary"]),
        leading_width=40,
        title=ft.Text("MoneyFlow Cloud", weight=ft.FontWeight.BOLD, size=20, color=colors["text"]),
        center_title=False,
        bgcolor=colors["surface"],
        actions=[
            ft.IconButton(icon=ft.Icons.LIGHTBULB_CIRCLE, icon_color="amber", tooltip="Consultar al Gurú IA",
                          on_click=lambda e: safe_call(abrir_chat_guru, page)()),
            ft.IconButton(icon=ft.Icons.PERSON_ROUNDED, icon_color=colors["primary"], tooltip="Perfil",
                          on_click=lambda e: safe_call(ir_a_perfil, page)()),
            ft.VerticalDivider(width=10),
        ],
    )

    def cambio_pestana(e):
        idx = e.control.selected_index
        if idx == 0: ejecutar_vista_dashboard(page)
        elif idx == 1: ir_a_movimientos_crud(page)
        elif idx == 2: ir_a_presupuestos(page)
        elif idx == 3: ejecutar_vista_estadisticas_segura(page)
        elif idx == 4: ir_a_configuracion_categorias(page)

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=lambda e: safe_call(cambio_pestana, e)(),
        bgcolor=colors["surface"],
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_ROUNDED, label="Inicio"),
            ft.NavigationBarDestination(icon=ft.Icons.ADD_ROAD_ROUNDED, label="Movimientos"),
            ft.NavigationBarDestination(icon=ft.Icons.MONEY_ROUNDED, label="Presupuesto"),
            ft.NavigationBarDestination(icon=ft.Icons.ANALYTICS_ROUNDED, label="Métricas"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_ACCESSIBILITY_ROUNDED, label="Categorías"),
        ]
    )

    page.add(ft.Container(content=columna_principal, padding=20, expand=True))
    ejecutar_vista_dashboard(page)

# ==================== MÉTODO RAÍZ ====================
def main(page: ft.Page):
    page.title = "MoneyFlow Premium Cloud"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 400
    page.window.height = 750
    
    import os as _os
    base_dir = _os.path.dirname(__file__)
    page.window.icon = _os.path.join(base_dir, "assets", "icono.ico")
    
    init_debugger(page)

    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://xwvebpdivouldkvfrogh.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    
    inicializar_supabase(SUPABASE_URL, SUPABASE_KEY)
    
    login_view(page)

if __name__ == "__main__":
    ft.run(main)