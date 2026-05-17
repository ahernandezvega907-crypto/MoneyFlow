import os
import sys
import io
import base64
import csv
import json
import hashlib
import threading
import random
import platform
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# ==================== CONFIGURACIÓN ====================
SUPABASE_URL = "https://xwvebpdivouldkvfrogh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh3dmVicGRpdm91bGRrdmZyb2doIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY2NTI1NTgsImV4cCI6MjA5MjIyODU1OH0.5eI8mdM3bR7SAPhqp0tcGPY02GUh3xuUQEvtRHNjU5s"
GEMINI_API_KEY = "AIzaSyBN6MswmbWs2I58iatqj3ZtsoMoPmDb4IU"

# ==================== IMPORTACIONES OPCIONALES (GRÁFICOS) ====================
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ==================== IMPORTACIONES OPCIONALES (IA) ====================
try:
    from google import genai
    GENAI_OK = True
except ImportError:
    GENAI_OK = False

# ==================== IMPORTACIONES PARA NOTIFICACIONES Y SCHEDULER ====================
try:
    from plyer import notification
    PLYER_OK = True
except ImportError:
    PLYER_OK = False

from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from dateutil.relativedelta import relativedelta

from supabase import create_client, Client
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors as reportlab_colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import flet as ft

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

client = None
if GENAI_OK and GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error al inicializar Gemini: {e}")
        client = None

# ==================== FUNCIÓN PARA VERIFICAR LICENCIA PREMIUM ====================
def is_premium():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    license_path = os.path.join(base_path, "license.key")
    return os.path.exists(license_path)

# ==================== PALETA DE COLORES DINÁMICA ====================
class AppColors:
    DARK = {
        "bg": "#0A0A0A",
        "surface": "#1E1E1E",
        "primary": "#00BFA6",
        "secondary": "#1E88E5",
        "success": "#00C853",
        "error": "#D32F2F",
        "text": "#FFFFFF",
        "text_secondary": "#B0B0B0",
    }
    LIGHT = {
        "bg": "#F5F5F5",
        "surface": "#FFFFFF",
        "primary": "#00796B",
        "secondary": "#1976D2",
        "success": "#2E7D32",
        "error": "#C62828",
        "text": "#000000",
        "text_secondary": "#555555",
    }

    @staticmethod
    def get(theme_mode):
        return AppColors.DARK if theme_mode == ft.ThemeMode.DARK else AppColors.LIGHT

# ==================== FORMATEO DE MONEDA ====================
CURRENCY_FORMATS = {
    "CRC": {"symbol": "₡", "thousands": ",", "decimal": "."},
    "USD": {"symbol": "$", "thousands": ",", "decimal": "."},
    "COP": {"symbol": "$", "thousands": ".", "decimal": ","},
    "EUR": {"symbol": "€", "thousands": ".", "decimal": ","},
    "MXN": {"symbol": "$", "thousands": ",", "decimal": "."},
}

def format_currency(amount, currency_code):
    fmt = CURRENCY_FORMATS.get(currency_code, CURRENCY_FORMATS["USD"])
    symbol = fmt["symbol"]
    thousands_sep = fmt["thousands"]
    decimal_sep = fmt["decimal"]

    amount = round(amount, 2)
    negative = amount < 0
    amount = abs(amount)

    int_part = int(amount)
    dec_part = int((amount - int_part) * 100 + 0.5)
    dec_str = f"{dec_part:02d}"

    int_str = f"{int_part:,}".replace(",", thousands_sep)

    result = f"{symbol}{int_str}{decimal_sep}{dec_str}"
    if negative:
        result = f"-{result}"
    return result

# ==================== CONSEJOS FINANCIEROS DIARIOS ====================
CONSEJOS = [
    "💡 Ahorra al menos el 10% de tus ingresos cada mes.",
    "📊 Revisa tus gastos semanalmente para detectar fugas.",
    "🍳 Cocinar en casa puede ahorrarte hasta un 50% en comida.",
    "🚫 Evita las compras impulsivas: espera 24 horas antes de decidir.",
    "📱 Compara precios en línea antes de comprar en tienda física.",
    "💳 Paga tus tarjetas de crédito a tiempo para evitar intereses.",
    "🎯 Define metas de ahorro claras y alcanzables.",
    "📅 Planifica tus comidas de la semana para evitar gastos innecesarios.",
    "🚗 Usa transporte público o comparte viajes para reducir gastos.",
    "🔔 Activa los recordatorios de pagos para nunca olvidar una factura.",
    "📈 Invierte en educación financiera: lee libros o cursos gratuitos.",
    "🏦 Compara comisiones bancarias y elige la cuenta que más te convenga.",
]

def consejo_del_dia():
    dia = datetime.now().timetuple().tm_yday
    return CONSEJOS[dia % len(CONSEJOS)]

# ==================== FUNCIONES DE BASE DE DATOS ====================
def verificar_conexion():
    try:
        supabase.table("categorias").select("count", count="exact").limit(0).execute()
        return True
    except:
        return False

def verificar_y_guia_configuracion(page):
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
);
INSERT INTO categorias (nombre, icono, user_id) VALUES
('Comida', 'restaurant', '00000000-0000-0000-0000-000000000001'),
('Transporte', 'directions_car', '00000000-0000-0000-0000-000000000001'),
('Ocio', 'movie', '00000000-0000-0000-0000-000000000001'),
('Salud', 'local_hospital', '00000000-0000-0000-0000-000000000001'),
('Compras', 'shopping_cart', '00000000-0000-0000-0000-000000000001'),
('Servicios', 'electrical_services', '00000000-0000-0000-0000-000000000001'),
('Otros', 'category', '00000000-0000-0000-0000-000000000001');
            """)
    try:
        supabase.table("presupuestos").select("count", count="exact").limit(0).execute()
    except Exception as e:
        if "does not exist" in str(e).lower():
            problemas.append("""
CREATE TABLE presupuestos (
  id SERIAL PRIMARY KEY,
  categoria_id INT REFERENCES categorias(id),
  monto_limite DECIMAL(10,2) NOT NULL,
  mes DATE NOT NULL,
  user_id UUID NOT NULL,
  UNIQUE(categoria_id, mes, user_id)
);
            """)
    try:
        supabase.table("gastos").select("categoria_id").limit(1).execute()
    except Exception as e:
        if "column" in str(e).lower() and "does not exist" in str(e).lower():
            problemas.append("ALTER TABLE gastos ADD COLUMN categoria_id INT REFERENCES categorias(id);")
    try:
        supabase.table("gastos").select("user_id").limit(1).execute()
    except Exception as e:
        if "column" in str(e).lower() and "does not exist" in str(e).lower():
            problemas.append("ALTER TABLE gastos ADD COLUMN user_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001';")
    try:
        supabase.table("recordatorios").select("count", count="exact").limit(0).execute()
    except Exception as e:
        if "does not exist" in str(e).lower():
            problemas.append("""
CREATE TABLE recordatorios (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL,
  titulo TEXT NOT NULL,
  monto DECIMAL(10,2),
  categoria_id INT REFERENCES categorias(id),
  fecha_inicio DATE NOT NULL,
  frecuencia TEXT NOT NULL DEFAULT 'mensual',
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
            """)
    try:
        supabase.table("rachas").select("user_id").limit(1).execute()
    except Exception as e:
        if "does not exist" in str(e).lower():
            problemas.append("""
CREATE TABLE rachas (
  user_id UUID PRIMARY KEY,
  ultima_fecha DATE,
  racha_actual INT DEFAULT 0,
  racha_maxima INT DEFAULT 0
);
            """)
    if problemas:
        contenido_sql = "\n\n".join(problemas)
        page.dialog = ft.AlertDialog(
            title=ft.Text("⚙️ Configuración inicial requerida", color=AppColors.DARK["primary"]),
            content=ft.Column([
                ft.Text("Ejecuta el siguiente SQL en Supabase:", size=14),
                ft.Container(content=ft.Text(contenido_sql, selectable=True, size=12, font_family="monospace"),
                             bgcolor="#2d2d2d", padding=10, border_radius=8),
                ft.Text("Luego reinicia la app.", size=14, color=AppColors.DARK["error"]),
            ], spacing=10, scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Entendido", on_click=lambda e: close_dialog(page))],
            actions_alignment=ft.MainAxisAlignment.CENTER,
        )
        page.dialog.open = True
        page.update()
        return False
    return True

def close_dialog(page, dlg=None):
    """Cierra un diálogo específico o el diálogo actual de page.dialog."""
    if dlg:
        dlg.open = False
        page.update()
    else:
        if page.dialog:
            page.dialog.open = False
            page.update()

# ==================== CATEGORÍAS (CON EMOJIS PERSONALIZABLES) ====================
EMOJI_LIST = ["🍔", "🚗", "🎬", "🏥", "🛍️", "⚡", "📚", "✈️", "🎵", "🏠", "🐾", "💻", "🎁", "🏋️", "☕", "💡"]

def cargar_categorias(user_id):
    try:
        res = supabase.table("categorias").select("id, nombre, icono, user_id").or_(
            f"user_id.eq.{user_id},user_id.eq.00000000-0000-0000-0000-000000000001"
        ).execute()
        datos = res.data if res.data else []
        propias = [c for c in datos if c["user_id"] == user_id]
        if not propias:
            globales = supabase.table("categorias").select("*").eq("user_id", "00000000-0000-0000-0000-000000000001").execute()
            if globales.data:
                for cat in globales.data:
                    supabase.table("categorias").insert({
                        "nombre": cat["nombre"],
                        "icono": cat.get("icono", "category"),
                        "user_id": user_id
                    }).execute()
            datos = supabase.table("categorias").select("id, nombre, icono, user_id").or_(
                f"user_id.eq.{user_id},user_id.eq.00000000-0000-0000-0000-000000000001"
            ).execute().data
        return datos
    except Exception as e:
        print("Error cargando categorías:", e)
        return []

def agregar_categoria(nombre, icono, user_id):
    return supabase.table("categorias").insert({
        "nombre": nombre,
        "icono": icono,
        "user_id": user_id
    }).execute()

def editar_categoria(categoria_id, nuevo_nombre, nuevo_icono):
    return supabase.table("categorias").update({
        "nombre": nuevo_nombre,
        "icono": nuevo_icono
    }).eq("id", categoria_id).execute()

def eliminar_categoria(categoria_id):
    return supabase.table("categorias").delete().eq("id", categoria_id).execute()

def cargar_gastos_con_categoria(user_id):
    try:
        res = supabase.table("gastos").select("*, categorias(nombre, icono)").order("created_at").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print("Error cargando gastos:", e)
        return []

def generar_grafico_tendencia(datos, theme_mode):
    if not MATPLOTLIB_OK:
        return None
    if not datos:
        return None
    colors = AppColors.get(theme_mode)
    gastos_por_mes = defaultdict(float)
    for g in datos:
        fecha_str = g.get("created_at")
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                mes_key = fecha.strftime("%Y-%m")
                gastos_por_mes[mes_key] += g.get("monto", 0)
            except:
                pass
    if not gastos_por_mes:
        return None
    meses_ordenados = sorted(gastos_por_mes.keys())
    montos = [gastos_por_mes[m] for m in meses_ordenados]
    plt.figure(figsize=(4, 2.5))
    plt.plot(meses_ordenados, montos, marker='o', color=colors["primary"], linewidth=2, markersize=4)
    plt.fill_between(meses_ordenados, montos, alpha=0.2, color=colors["primary"])
    plt.title("Evolución mensual de gastos", fontsize=10, color=colors["text"])
    plt.xlabel("Mes", fontsize=8, color=colors["text_secondary"])
    plt.ylabel("Gasto total", fontsize=8, color=colors["text_secondary"])
    plt.xticks(rotation=45, ha='right', fontsize=7, color=colors["text_secondary"])
    plt.yticks(fontsize=7, color=colors["text_secondary"])
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', facecolor=colors["bg"])
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    plt.close()
    return ft.Image(src=f"data:image/png;base64,{img_str}", width=350, height=200)

def generar_grafico_gastos(datos, theme_mode):
    if not MATPLOTLIB_OK:
        return None
    if not datos:
        return None
    colors = AppColors.get(theme_mode)
    resumen = {}
    for g in datos:
        nombre = g.get("nombre", "Sin nombre")
        monto = g.get("monto", 0)
        resumen[nombre] = resumen.get(nombre, 0) + monto
    items = sorted(resumen.items(), key=lambda x: x[1], reverse=True)[:5]
    if not items:
        return None
    labels, sizes = zip(*items)
    plt.figure(figsize=(3, 3))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90,
            colors=[colors["primary"], colors["secondary"], "#FFB74D", "#E57373", "#BA68C8"],
            wedgeprops=dict(width=0.5, edgecolor=colors["bg"]))
    plt.axis('equal')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', facecolor=colors["bg"])
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode()
    plt.close()
    return ft.Image(src=f"data:image/png;base64,{img_str}", width=180, height=180)

def mostrar_snackbar(page, texto, color):
    page.snack_bar = ft.SnackBar(content=ft.Text(texto), bgcolor=color, action="OK")
    page.snack_bar.open = True
    page.update()

# ==================== MONITOREO DE CONEXIÓN (CORREGIDO) ====================
def iniciar_monitoreo_conexion(page, estado_conexion, online_ref, sincronizando_ref, sincronizar_callback):
    timer = None

    def verificar():
        nonlocal timer
        if page.session is None:
            return
        online_anterior = online_ref[0]
        conectado = verificar_conexion()
        online_ref[0] = conectado
        if conectado != online_anterior:
            try:
                if sincronizando_ref[0]:
                    estado_conexion.value = "⏳ Sincronizando..."
                    estado_conexion.color = AppColors.get(page.theme_mode)["text_secondary"]
                elif conectado:
                    estado_conexion.value = "🟢 Conectado"
                    estado_conexion.color = AppColors.get(page.theme_mode)["success"]
                else:
                    estado_conexion.value = "🔴 Sin conexión"
                    estado_conexion.color = AppColors.get(page.theme_mode)["error"]
                page.update()
            except RuntimeError:
                return
        timer = threading.Timer(30.0, verificar)
        timer.start()

    timer = threading.Timer(30.0, verificar)
    timer.start()

    def cancelar():
        if timer:
            timer.cancel()
    return cancelar

# ==================== GUARDADO DE ARCHIVOS ====================
def guardar_archivo_en_carpeta(page, nombre_archivo, contenido_bytes, subcarpeta="exportaciones", colors=None):
    try:
        import tempfile
        temp_dir = tempfile.gettempdir()
        export_path = os.path.join(temp_dir, nombre_archivo)
        with open(export_path, "wb") as f:
            f.write(contenido_bytes)
        msg = f"✓ Guardado en: {export_path}"
    except Exception as e:
        msg = f"❌ Error al guardar: {e}"
    color = colors["success"] if colors else "#00C853"
    mostrar_snackbar(page, msg, color)

# ==================== SISTEMA DE PIN DE ACCESO ====================
def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def get_pin_file_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "pin_hash.txt")

def save_pin_hash(pin):
    with open(get_pin_file_path(), "w") as f:
        f.write(hash_pin(pin))

def load_pin_hash():
    path = get_pin_file_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return None

def solicitar_pin(page, on_correct_pin):
    colors = AppColors.get(page.theme_mode)
    page.clean()
    page.bgcolor = colors["bg"]
    
    pin_input = ft.TextField(
        label="PIN de acceso",
        password=True,
        keyboard_type=ft.KeyboardType.NUMBER,
        max_length=4,
        width=150,
        text_align=ft.TextAlign.CENTER,
        border_radius=16,
        bgcolor=colors["surface"],
        color=colors["text"],
    )
    error_text = ft.Text("", color=colors["error"])
    saved_hash = load_pin_hash()

    def verificar(e):
        entered = pin_input.value.strip()
        if not entered or len(entered) != 4:
            error_text.value = "Ingresa un PIN de 4 dígitos"
            page.update()
            return
        if saved_hash is None:
            save_pin_hash(entered)
            mostrar_snackbar(page, "PIN configurado correctamente", colors["success"])
            page.clean()
            on_correct_pin()
        elif hash_pin(entered) == saved_hash:
            page.clean()
            on_correct_pin()
        else:
            error_text.value = "PIN incorrecto"
            pin_input.value = ""
            page.update()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("🔐 Ingresa tu PIN", size=24, weight="bold", color=colors["primary"]),
                ft.Text("Protege tu información financiera", size=14, color=colors["text_secondary"]),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                pin_input,
                ft.Button("Acceder", on_click=verificar, style=ft.ButtonStyle(bgcolor=colors["primary"], color=colors["bg"])),
                error_text,
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
            padding=20,
            expand=True,
            alignment=ft.Alignment.CENTER
        )
    )
    page.update()

def cambiar_pin(page):
    colors = AppColors.get(page.theme_mode)
    
    old_pin = ft.TextField(label="PIN actual", password=True, max_length=4, width=150, text_align=ft.TextAlign.CENTER)
    new_pin_input = ft.TextField(label="Nuevo PIN", password=True, max_length=4, width=150, text_align=ft.TextAlign.CENTER)
    confirm_pin_input = ft.TextField(label="Confirmar PIN", password=True, max_length=4, width=150, text_align=ft.TextAlign.CENTER)
    error_old = ft.Text("", color=colors["error"])
    error_new = ft.Text("", color=colors["error"])

    dlg_content = ft.Column([old_pin, error_old])
    dlg = ft.AlertDialog(
        title=ft.Text("Cambiar PIN"),
        content=dlg_content,
        actions=[
            ft.TextButton("Verificar", on_click=lambda e: verificar_viejo()),
            ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def verificar_viejo():
        old = old_pin.value.strip()
        saved_hash = load_pin_hash()
        if saved_hash and hash_pin(old) != saved_hash:
            error_old.value = "PIN actual incorrecto"
            page.update()
            return
        dlg_content.controls.clear()
        dlg_content.controls.append(new_pin_input)
        dlg_content.controls.append(confirm_pin_input)
        dlg_content.controls.append(error_new)
        dlg.actions = [
            ft.TextButton("Guardar", on_click=lambda e: guardar_nuevo()),
            ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg)),
        ]
        page.update()

    def guardar_nuevo():
        new1 = new_pin_input.value.strip()
        new2 = confirm_pin_input.value.strip()
        if not new1 or len(new1) != 4 or new1 != new2:
            error_new.value = "El PIN debe ser de 4 dígitos y coincidir"
            page.update()
            return
        save_pin_hash(new1)
        close_dialog(page, dlg)
        mostrar_snackbar(page, "PIN actualizado correctamente", colors["success"])

    page.show_dialog(dlg)

# ==================== PANTALLA DE LOGIN ====================
def login_view(page: ft.Page):
    page.clean()
    colors = AppColors.get(page.theme_mode)
    page.bgcolor = colors["bg"]
    page.padding = 20

    email_input = ft.TextField(label="Email", border_radius=16, bgcolor=colors["surface"], color=colors["text"])
    password_input = ft.TextField(label="Contraseña", password=True, border_radius=16, bgcolor=colors["surface"], color=colors["text"])
    error_text = ft.Text("", color=colors["error"])

    def do_login(e):
        try:
            res = supabase.auth.sign_in_with_password({"email": email_input.value, "password": password_input.value})
            page.user_id = res.user.id
            page.user_email = res.user.email
            solicitar_pin(page, lambda: main_app(page))
        except Exception as ex:
            error_text.value = f"Error: {str(ex)[:100]}"
            page.update()

    def do_register(e):
        try:
            res = supabase.auth.sign_up({"email": email_input.value, "password": password_input.value})
            if res.user:
                user_id = res.user.id
                default_cats = supabase.table("categorias").select("*").eq("user_id", "00000000-0000-0000-0000-000000000001").execute()
                if default_cats.data:
                    for cat in default_cats.data:
                        supabase.table("categorias").insert({
                            "nombre": cat["nombre"],
                            "icono": cat["icono"],
                            "user_id": user_id
                        }).execute()
                mostrar_snackbar(page, "Usuario registrado. Ahora inicia sesión.", colors["success"])
                email_input.value = ""
                password_input.value = ""
                error_text.value = ""
            else:
                error_text.value = "Error al registrar. Intenta con otro email."
        except Exception as ex:
            error_text.value = f"Error: {str(ex)[:100]}"
        page.update()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Text("MoneyFlow", size=32, weight="bold", color=colors["primary"]),
                ft.Text("Inicia sesión o regístrate", size=14, color=colors["text_secondary"]),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                email_input,
                password_input,
                ft.Row([
                    ft.Button("Iniciar sesión", on_click=do_login, style=ft.ButtonStyle(bgcolor=colors["primary"], color=colors["bg"])),
                    ft.Button("Registrarse", on_click=do_register, style=ft.ButtonStyle(bgcolor=colors["surface"], color=colors["text"])),
                ], wrap=True, run_spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                error_text,
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
            padding=20,
            expand=True,
            alignment=ft.Alignment.CENTER
        )
    )

# ==================== APLICACIÓN PRINCIPAL ====================
def main_app(page: ft.Page):
    if not hasattr(page, "user_id") or not page.user_id:
        login_view(page)
        return

    user_id = page.user_id
    user_email = page.user_email
    premium = is_premium()

    # ---- PUNTO 7: Carga del tema con soporte para SYSTEM ----
    saved_theme = None
    if hasattr(page, "client_storage"):
        saved_theme = page.client_storage.get("theme_mode")
    if saved_theme == "SYSTEM":
        page.theme_mode = ft.ThemeMode.SYSTEM
    elif saved_theme == "LIGHT":
        page.theme_mode = ft.ThemeMode.LIGHT
    elif saved_theme == "DARK":
        page.theme_mode = ft.ThemeMode.DARK
    else:
        page.theme_mode = ft.ThemeMode.DARK

    colors = AppColors.get(page.theme_mode)
    page.bgcolor = colors["bg"]

    currency = "CRC"
    if hasattr(page, "client_storage"):
        currency = page.client_storage.get("currency") or "CRC"
    currency_symbol = CURRENCY_FORMATS[currency]["symbol"]

    recordatorios_activos = True
    if hasattr(page, "client_storage"):
        recordatorios_activos = page.client_storage.get("recordatorios") != "false"

    online = [True]
    sincronizando = [False]

    categorias = cargar_categorias(user_id)
    if not categorias:
        page.add(ft.Text("Error cargando categorías. Revisa conexión.", color=colors["error"]))
        return

    opciones_categorias = [
        ft.dropdown.Option(key=str(c["id"]), text=f"{c.get('icono','')}  {c['nombre']}")
        for c in categorias
    ]

    input_nombre = ft.TextField(label="¿En qué gastaste?", border_radius=16,
                                border_color=colors["text_secondary"], focused_border_color=colors["primary"],
                                bgcolor=colors["surface"], color=colors["text"], expand=True)
    input_monto = ft.TextField(label="Monto", border_radius=16, border_color=colors["text_secondary"],
                               focused_border_color=colors["primary"],
                               prefix=ft.Text(f"{currency_symbol} ", size=14),
                               bgcolor=colors["surface"], color=colors["text"], expand=True)
    categoria_dropdown = ft.Dropdown(label="Categoría", options=opciones_categorias,
                                     value=opciones_categorias[0].key if opciones_categorias else None, expand=True)

    contenedor_historial = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=12)
    chat_display = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=10)
    chat_display.controls.append(
        ft.Text("💡 Pregunta al Guru para recibir consejos financieros.", italic=True, color=colors["text_secondary"]))
    input_chat = ft.TextField(hint_text="Pregunta al Guru...", expand=True, border_radius=30,
                              border_color=colors["text_secondary"], focused_border_color=colors["primary"],
                              bgcolor=colors["surface"], color=colors["text"])
    grafico_container = ft.Container(visible=False, alignment=ft.Alignment.CENTER, padding=10)
    tendencia_container = ft.Container(visible=False, alignment=ft.Alignment.CENTER, padding=10)
    presupuestos_grid = ft.Column(spacing=15, scroll=ft.ScrollMode.ALWAYS)
    dashboard_grid = ft.Column(spacing=15, scroll=ft.ScrollMode.ALWAYS, expand=True)
    perfil_contenido = ft.Column(spacing=20, scroll=ft.ScrollMode.AUTO, expand=True)

    estado_conexion = ft.Text("⏳ Verificando...", size=12, color=colors["text_secondary"])

    # ==================== NOTIFICACIONES Y RECORDATORIOS ====================
    def mostrar_notificacion(titulo, mensaje, tipo="info"):
        if PLYER_OK:
            try:
                notification.notify(
                    title=f"MoneyFlow – {titulo}",
                    message=mensaje,
                    app_name="MoneyFlow",
                    timeout=10
                )
            except Exception as e:
                print("Error notificación nativa:", e)
        icono = {"info": ft.Icons.NOTIFICATIONS_ACTIVE, "alerta": ft.Icons.WARNING, "error": ft.Icons.ERROR}.get(tipo, ft.Icons.NOTIFICATIONS_ACTIVE)
        color_fondo = {"info": colors["primary"], "alerta": colors["secondary"], "error": colors["error"]}.get(tipo, colors["primary"])
        banner = ft.Banner(
            bgcolor=color_fondo,
            leading=ft.Icon(icono, color=colors["text"], size=30),
            content=ft.Text(f"{titulo}: {mensaje}", color=colors["bg"]),
            actions=[ft.TextButton("OK", on_click=lambda e: page.close(banner))],
        )
        page.open(banner)
        page.update()

    def calcular_proxima_fecha(fecha_actual, frecuencia):
        if frecuencia == 'unico':
            return None
        elif frecuencia == 'semanal':
            return fecha_actual + relativedelta(weeks=1)
        elif frecuencia == 'mensual':
            return fecha_actual + relativedelta(months=1)
        elif frecuencia == 'anual':
            return fecha_actual + relativedelta(years=1)
        return None

    def verificar_alertas_presupuesto():
        if not recordatorios_activos:
            return
        mes_actual = datetime.now().replace(day=1).date().isoformat()
        for cat in categorias:
            cat_id = cat["id"]
            try:
                pres = supabase.table("presupuestos").select("monto_limite") \
                    .eq("categoria_id", cat_id).eq("user_id", user_id).eq("mes", mes_actual).execute()
                if not pres.data:
                    continue
                limite = pres.data[0]["monto_limite"]
                gastos_cat = supabase.table("gastos").select("monto") \
                    .eq("categoria_id", cat_id).eq("user_id", user_id) \
                    .gte("created_at", mes_actual).execute()
                gastado = sum(g["monto"] for g in (gastos_cat.data or []))
                if limite <= 0:
                    continue
                porcentaje = (gastado / limite) * 100
                if porcentaje >= 100:
                    mostrar_notificacion(
                        f"🚨 Presupuesto agotado en {cat['nombre']}",
                        f"Has gastado {format_currency(gastado, currency)} de {format_currency(limite, currency)}",
                        "error"
                    )
                elif porcentaje >= 80:
                    mostrar_notificacion(
                        f"⚠️ {cat['nombre']} al {porcentaje:.0f}%",
                        f"Quedan {format_currency(limite - gastado, currency)} para el mes",
                        "alerta"
                    )
            except:
                pass

    def actualizar_racha():
        hoy = datetime.now().date()
        try:
            res = supabase.table("rachas").select("*").eq("user_id", user_id).execute()
            if res.data:
                racha = res.data[0]
                ultima = racha["ultima_fecha"]
                ultima = datetime.fromisoformat(ultima).date() if ultima else None
                if ultima == hoy:
                    return
                elif ultima == hoy - timedelta(days=1):
                    nueva_racha = racha["racha_actual"] + 1
                    racha_max = max(racha["racha_maxima"], nueva_racha)
                else:
                    nueva_racha = 1
                    racha_max = racha["racha_maxima"]
                supabase.table("rachas").update({
                    "ultima_fecha": hoy.isoformat(),
                    "racha_actual": nueva_racha,
                    "racha_maxima": racha_max
                }).eq("user_id", user_id).execute()
                if nueva_racha in (3, 7, 14, 30, 60, 100):
                    mostrar_notificacion(
                        "🔥 ¡Racha imparable!",
                        f"{nueva_racha} días seguidos registrando gastos. ¡Eres increíble!",
                        "info"
                    )
            else:
                supabase.table("rachas").insert({
                    "user_id": user_id,
                    "ultima_fecha": hoy.isoformat(),
                    "racha_actual": 1,
                    "racha_maxima": 1
                }).execute()
        except Exception as e:
            print("Error racha:", e)

    def job_revisar():
        if not recordatorios_activos or not online[0]:
            return
        hoy = datetime.now().date()
        try:
            res = supabase.table("recordatorios").select("*") \
                .eq("user_id", user_id) \
                .eq("activo", True) \
                .lte("fecha_inicio", hoy.isoformat()) \
                .execute()
            for rec in (res.data or []):
                monto_str = format_currency(rec.get("monto", 0), currency)
                mostrar_notificacion(
                    f"🔔 Recordatorio: {rec['titulo']}",
                    f"Vence hoy. Monto: {monto_str}",
                    "alerta"
                )
                if rec["frecuencia"] != "unico":
                    nueva = calcular_proxima_fecha(hoy, rec["frecuencia"])
                    if nueva:
                        supabase.table("recordatorios").update({"fecha_inicio": nueva.isoformat()}).eq("id", rec["id"]).execute()
                    else:
                        supabase.table("recordatorios").update({"activo": False}).eq("id", rec["id"]).execute()
                else:
                    supabase.table("recordatorios").update({"activo": False}).eq("id", rec["id"]).execute()
        except Exception as e:
            print("Error job recordatorios:", e)
        verificar_alertas_presupuesto()

    # ==================== FIN NOTIFICACIONES ====================

    def actualizar_estado_conexion():
        if sincronizando[0]:
            estado_conexion.value = "⏳ Sincronizando..."
            estado_conexion.color = colors["text_secondary"]
        elif online[0]:
            estado_conexion.value = "🟢 Conectado"
            estado_conexion.color = colors["success"]
        else:
            estado_conexion.value = "🔴 Sin conexión"
            estado_conexion.color = colors["error"]
        page.update()

    def sincronizar_datos(silencioso=False):
        if sincronizando[0]:
            return
        sincronizando[0] = True
        actualizar_estado_conexion()
        
        exito = True
        try:
            if not verificar_conexion():
                online[0] = False
                exito = False
            else:
                online[0] = True
                nonlocal categorias, opciones_categorias
                categorias = cargar_categorias(user_id)
                opciones_categorias = [
                    ft.dropdown.Option(key=str(c["id"]), text=f"{c.get('icono','')}  {c['nombre']}")
                    for c in categorias
                ]
                categoria_dropdown.options = opciones_categorias
                if opciones_categorias:
                    categoria_dropdown.value = opciones_categorias[0].key
                
                actualizar_lista_visual()
                if vista_presupuestos.visible:
                    cargar_presupuestos()
                if vista_dashboard.visible:
                    cargar_dashboard()

                if recordatorios_activos:
                    gastos_hoy = [g for g in cargar_gastos_con_categoria(user_id)
                                  if g.get("created_at", "").startswith(datetime.now().strftime("%Y-%m-%d"))]
                    if not gastos_hoy:
                        mostrar_notificacion("📅 ¡Buenos días!", "No has registrado gastos hoy. ¡Recuerda anotarlos!", "info")
                verificar_alertas_presupuesto()
        except Exception as e:
            online[0] = False
            exito = False
        finally:
            sincronizando[0] = False
            actualizar_estado_conexion()
            if not silencioso and exito and online[0]:
                mostrar_snackbar(page, "✅ Datos sincronizados", colors["success"])
            elif not silencioso and not online[0]:
                mostrar_snackbar(page, "❌ Sin conexión a Internet", colors["error"])

    # ==================== EXPORTACIONES ====================
    def exportar_csv(e):
        gastos = cargar_gastos_con_categoria(user_id)
        if not gastos:
            mostrar_snackbar(page, "No hay gastos para exportar", colors["error"])
            return
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Fecha", "Nombre", "Monto", "Categoría"])
        for g in gastos:
            cat = g.get("categorias", {})
            nombre_cat = cat.get("nombre", "") if isinstance(cat, dict) else ""
            fecha = g.get("created_at", datetime.now().isoformat())
            writer.writerow([fecha, g.get("nombre", ""), g.get("monto", 0), nombre_cat])
        output.seek(0)
        data_bytes = output.getvalue().encode("utf-8")
        output.close()
        guardar_archivo_en_carpeta(page, "gastos.csv", data_bytes, colors=colors)

    def exportar_excel(e):
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium", colors["error"])
            return
        gastos = cargar_gastos_con_categoria(user_id)
        if not gastos:
            mostrar_snackbar(page, "No hay gastos para exportar", colors["error"])
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "Gastos MoneyFlow"
        ws.append(["Fecha", "Nombre", "Monto", "Categoría"])
        for g in gastos:
            cat = g.get("categorias", {})
            nombre_cat = cat.get("nombre", "") if isinstance(cat, dict) else ""
            fecha = g.get("created_at", datetime.now().isoformat())
            ws.append([fecha, g.get("nombre", ""), g.get("monto", 0), nombre_cat])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        data_bytes = output.getvalue()
        output.close()
        guardar_archivo_en_carpeta(page, "gastos.xlsx", data_bytes, colors=colors)

    def exportar_pdf(e):
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium", colors["error"])
            return
        gastos = cargar_gastos_con_categoria(user_id)
        if not gastos:
            mostrar_snackbar(page, "No hay gastos para exportar", colors["error"])
            return
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        title = Paragraph("Informe de Gastos - MoneyFlow", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2 * inch))
        data = [["Fecha", "Nombre", "Monto", "Categoría"]]
        total = 0
        for g in gastos:
            cat = g.get("categorias", {})
            nombre_cat = cat.get("nombre", "") if isinstance(cat, dict) else ""
            fecha = g.get("created_at", datetime.now().isoformat())[:10]
            monto = g.get("monto", 0)
            total += monto
            data.append([fecha, g.get("nombre", ""), format_currency(monto, currency), nombre_cat])
        data.append(["", "", f"Total: {format_currency(total, currency)}", ""])
        table = Table(data, colWidths=[1.5 * inch, 2 * inch, 1 * inch, 1.5 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), reportlab_colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), reportlab_colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), reportlab_colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, reportlab_colors.black),
        ]))
        story.append(table)
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        guardar_archivo_en_carpeta(page, "gastos.pdf", pdf_bytes, colors=colors)

    # ==================== BACKUP Y RESTAURACIÓN (PUNTO 8) ====================
    def exportar_backup(e):
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium requerida", colors["error"])
            return
        try:
            backup = {
                "version": "1.0",
                "fecha": datetime.now().isoformat(),
                "categorias": cargar_categorias(user_id),
                "gastos": cargar_gastos_con_categoria(user_id),
                "presupuestos": supabase.table("presupuestos").select("*").eq("user_id", user_id).execute().data,
                "recordatorios": supabase.table("recordatorios").select("*").eq("user_id", user_id).execute().data,
                "rachas": supabase.table("rachas").select("*").eq("user_id", user_id).execute().data,
            }
            json_bytes = json.dumps(backup, indent=2, default=str).encode("utf-8")
            guardar_archivo_en_carpeta(page, "moneyflow_backup.json", json_bytes, colors=colors)
        except Exception as ex:
            mostrar_snackbar(page, f"Error al exportar backup: {ex}", colors["error"])

    def importar_backup(e):
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium requerida", colors["error"])
            return

        def seleccionar_archivo():
            picker = ft.FilePicker()
            picker.on_result = lambda r: procesar_archivo_backup(r.files[0].path if r.files else None)
            page.overlay.append(picker)
            page.update()
            picker.pick_files(allow_multiple=False, file_type="custom", allowed_extensions=["json"])

        def procesar_archivo_backup(ruta_archivo):
            if not ruta_archivo:
                return
            try:
                with open(ruta_archivo, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not all(k in data for k in ("categorias", "gastos", "presupuestos", "recordatorios", "rachas")):
                    mostrar_snackbar(page, "Formato de backup inválido", colors["error"])
                    return
                for tabla in ["gastos", "presupuestos", "recordatorios", "rachas"]:
                    supabase.table(tabla).delete().eq("user_id", user_id).execute()
                supabase.table("categorias").delete().neq("user_id", "00000000-0000-0000-0000-000000000001").eq("user_id", user_id).execute()

                for cat in data["categorias"]:
                    if cat.get("user_id") != "00000000-0000-0000-0000-000000000001":
                        supabase.table("categorias").insert(cat).execute()
                for gasto in data["gastos"]:
                    supabase.table("gastos").insert(gasto).execute()
                for pres in data["presupuestos"]:
                    supabase.table("presupuestos").insert(pres).execute()
                for rec in data["recordatorios"]:
                    supabase.table("recordatorios").insert(rec).execute()
                if data["rachas"]:
                    supabase.table("rachas").insert(data["rachas"][0]).execute()

                mostrar_snackbar(page, "✅ Backup restaurado con éxito", colors["success"])
                page.clean()
                main_app(page)
            except Exception as ex:
                mostrar_snackbar(page, f"Error al importar: {ex}", colors["error"])

        dlg = ft.AlertDialog(
            title=ft.Text("Importar Backup"),
            content=ft.Text("Selecciona el archivo JSON de backup.\n"
                            "⚠️ Se reemplazarán todos tus datos actuales."),
            actions=[
                ft.TextButton("Seleccionar archivo", on_click=lambda e: seleccionar_archivo()),
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    # ==================== PUNTO 9: LECTURA DE SMS ====================
    def categorizar_por_sms(texto):
        texto = texto.lower()
        if any(p in texto for p in ["super", "mercado", "maxi", "pali", "walmart", "masxmenos"]):
            return "Supermercado"
        if any(p in texto for p in ["restaurante", "soda", "bar", "cafe", "comida"]):
            return "Comida"
        if any(p in texto for p in ["gasolinera", "gas", "combustible", "servicentro"]):
            return "Transporte"
        if any(p in texto for p in ["farmacia", "medicina", "hospital", "clínica"]):
            return "Salud"
        if any(p in texto for p in ["cine", "teatro", "concierto", "netflix", "spotify"]):
            return "Ocio"
        if any(p in texto for p in ["tienda", "compra", "amazon", "mercado libre"]):
            return "Compras"
        if any(p in texto for p in ["luz", "agua", "internet", "cable", "servicio", "electricidad"]):
            return "Servicios"
        return "Bancario"

    def extraer_transacciones_sms(lista_mensajes):
        import re
        transacciones = []
        for msg in lista_mensajes:
            if isinstance(msg, dict):
                texto = msg.get('body', '')
            else:
                texto = str(msg)
            matches = re.findall(r'\$?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?', texto)
            for match in matches:
                monto_str = match.replace('$', '').replace(',', '')
                try:
                    monto = float(monto_str)
                    if monto <= 0:
                        continue
                except:
                    continue
                categoria = categorizar_por_sms(texto)
                transacciones.append({
                    "monto": monto,
                    "descripcion": f"SMS: {texto[:50]}",
                    "categoria_sugerida": categoria,
                    "texto_original": texto
                })
        return transacciones

    def importar_sms(e):
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium", colors["error"])
            return

        if platform.system() == "Android":
            try:
                from plyer import sms
                sms.request()
                mensajes = sms.get(count=50)
                trans = extraer_transacciones_sms(mensajes)
                if trans:
                    mostrar_dialogo_revision_sms(trans)
                else:
                    mostrar_snackbar(page, "No se detectaron transacciones en los SMS", colors["secondary"])
            except Exception as ex:
                mostrar_snackbar(page, f"Error al leer SMS: {ex}", colors["error"])
        else:
            def procesar_pegado(e):
                texto = texto_sms.value
                if not texto.strip():
                    return
                lineas = [l.strip() for l in texto.split('\n') if l.strip()]
                trans = extraer_transacciones_sms(lineas)
                close_dialog(page, dlg_entrada)
                if trans:
                    mostrar_dialogo_revision_sms(trans)
                else:
                    mostrar_snackbar(page, "No se detectaron transacciones", colors["secondary"])

            texto_sms = ft.TextField(
                label="Pega aquí los SMS (uno por línea)",
                multiline=True,
                min_lines=4,
                max_lines=8,
                hint_text="Banco: Compra en Supermercado X por ₡45,000.00\n...",
            )
            dlg_entrada = ft.AlertDialog(
                title=ft.Text("Importar SMS (escritorio)"),
                content=ft.Column([texto_sms], scroll=ft.ScrollMode.AUTO),
                actions=[
                    ft.TextButton("Procesar", on_click=procesar_pegado),
                    ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg_entrada)),
                ],
            )
            page.show_dialog(dlg_entrada)

    def mostrar_dialogo_revision_sms(transacciones):
        checks = []
        for i, t in enumerate(transacciones):
            monto_str = format_currency(t["monto"], currency)
            check = ft.Checkbox(label=f"{t['categoria_sugerida']}: {t['descripcion']} - {monto_str}", value=True)
            checks.append(check)
            check.data = t

        def confirmar_importacion(e):
            seleccionadas = [c.data for c in checks if c.value]
            if not seleccionadas:
                mostrar_snackbar(page, "No seleccionaste ninguna transacción", colors["error"])
                return
            cats_existentes = {cat["nombre"].lower(): cat for cat in categorias}
            for t in seleccionadas:
                nombre_cat = t["categoria_sugerida"]
                cat = cats_existentes.get(nombre_cat.lower())
                if not cat:
                    res = agregar_categoria(nombre_cat, "📦", user_id)
                    if res.data:
                        cat = res.data[0]
                        cats_existentes[nombre_cat.lower()] = cat
                        categorias.append(cat)
                if cat:
                    supabase.table("gastos").insert({
                        "nombre": t["descripcion"][:50],
                        "monto": t["monto"],
                        "categoria_id": cat["id"],
                        "user_id": user_id
                    }).execute()
            close_dialog(page, dlg_revision)
            mostrar_snackbar(page, f"✅ {len(seleccionadas)} gastos importados", colors["success"])
            actualizar_lista_visual()

        dlg_revision = ft.AlertDialog(
            title=ft.Text("Revisar transacciones detectadas"),
            content=ft.Column(checks, scroll=ft.ScrollMode.AUTO, expand=True),
            actions=[
                ft.TextButton("Importar seleccionados", on_click=confirmar_importacion),
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg_revision)),
            ],
        )
        page.show_dialog(dlg_revision)

    # ==================== PERFIL DE USUARIO (PUNTO 10) ====================
    def cargar_perfil():
        perfil_contenido.controls.clear()
        try:
            user = supabase.auth.get_user()
            metadata = user.user.user_metadata if user.user.user_metadata else {}
            nombre = metadata.get("full_name", "")
            avatar_url = metadata.get("avatar_url", "")
        except Exception as e:
            nombre = ""
            avatar_url = ""

        if avatar_url:
            avatar = ft.CircleAvatar(
                foreground_image_url=avatar_url,
                radius=50,
                bgcolor=colors["primary"],
            )
        else:
            avatar = ft.CircleAvatar(
                content=ft.Text(nombre[:1].upper() if nombre else user_email[:1].upper(), size=32, color=colors["bg"]),
                radius=50,
                bgcolor=colors["primary"],
            )

        nombre_input = ft.TextField(label="Nombre completo", value=nombre, expand=True, border_radius=16,
                                    bgcolor=colors["surface"], color=colors["text"])

        def seleccionar_avatar(e):
            picker = ft.FilePicker()
            picker.on_result = lambda r: subir_avatar_desde_picker(r)
            page.overlay.append(picker)
            page.update()
            picker.pick_files(allow_multiple=False, file_type="image")

        def subir_avatar_desde_picker(resultado):
            if resultado.files:
                archivo = resultado.files[0].path
                subir_avatar_desde_ruta(archivo)

        def subir_avatar_desde_ruta(ruta_archivo):
            try:
                with open(ruta_archivo, "rb") as f:
                    supabase.storage.from_("avatars").upload(
                        f"{user_id}.jpg", f.read(), {"content-type": "image/jpeg"}
                    )
                avatar_url = supabase.storage.from_("avatars").get_public_url(f"{user_id}.jpg")
                supabase.auth.update_user({"data": {"avatar_url": avatar_url}})
                cargar_perfil()
                mostrar_snackbar(page, "Avatar actualizado", colors["success"])
            except Exception as ex:
                mostrar_snackbar(page, f"Error al subir avatar: {ex}", colors["error"])

        def cambiar_password(e):
            dlg_password = ft.AlertDialog(
                title=ft.Text("Cambiar contraseña"),
                content=ft.Column([
                    ft.TextField(label="Nueva contraseña", password=True, border_radius=16, bgcolor=colors["surface"], color=colors["text"]),
                    ft.TextField(label="Confirmar contraseña", password=True, border_radius=16, bgcolor=colors["surface"], color=colors["text"]),
                ]),
                actions=[
                    ft.TextButton("Guardar", on_click=lambda e: actualizar_password(e)),
                    ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg_password)),
                ],
            )
            page.show_dialog(dlg_password)

        def actualizar_password(e):
            nuevos = dlg_password.content.controls
            new_pass = nuevos[0].value
            confirm_pass = nuevos[1].value
            if not new_pass or new_pass != confirm_pass:
                mostrar_snackbar(page, "Las contraseñas no coinciden", colors["error"])
                return
            try:
                supabase.auth.update_user({"password": new_pass})
                close_dialog(page, dlg_password)
                mostrar_snackbar(page, "Contraseña actualizada", colors["success"])
            except Exception as ex:
                mostrar_snackbar(page, f"Error: {ex}", colors["error"])

        def guardar_perfil(e):
            nuevo_nombre = nombre_input.value.strip()
            metadata_update = {"full_name": nuevo_nombre}
            try:
                supabase.auth.update_user({"data": metadata_update})
                mostrar_snackbar(page, "Perfil actualizado", colors["success"])
                cargar_perfil()
            except Exception as ex:
                mostrar_snackbar(page, f"Error: {ex}", colors["error"])

        perfil_contenido.controls.extend([
            ft.Row([avatar, ft.TextButton("Cambiar foto", on_click=seleccionar_avatar)], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(),
            ft.Text("Información personal", size=18, weight="bold", color=colors["text"]),
            nombre_input,
            ft.Text(f"Email: {user_email}", color=colors["text_secondary"]),
            ft.Row([
                ft.FilledButton("Guardar cambios", on_click=guardar_perfil, icon=ft.Icons.SAVE),
                ft.OutlinedButton("Cambiar contraseña", on_click=cambiar_password, icon=ft.Icons.LOCK),
            ], wrap=True, spacing=10),
            ft.Divider(),
            ft.Text("Estado de la cuenta", size=18, weight="bold", color=colors["text"]),
            ft.Row([
                ft.Icon(ft.Icons.STAR if premium else ft.Icons.STAR_BORDER, color=colors["primary"] if premium else colors["text_secondary"]),
                ft.Text("Premium" if premium else "Gratuito", size=16, color=colors["primary"] if premium else colors["text_secondary"]),
                ft.TextButton("Adquirir Premium" if not premium else "Activado", on_click=lambda e: mostrar_snackbar(page, "Función no disponible aún", colors["secondary"])) if not premium else ft.Text(""),
            ]),
            ft.Divider(),
            ft.Text("Configuración", size=18, weight="bold", color=colors["text"]),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.SETTINGS),
                title=ft.Text("Abrir configuración"),
                on_click=lambda e: abrir_configuracion(e),
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOGOUT),
                title=ft.Text("Cerrar sesión"),
                on_click=logout,
            ),
        ])
        page.update()

    # ==================== PRESUPUESTOS ====================
    def cargar_presupuestos():
        presupuestos_grid.controls.clear()
        cats = cargar_categorias(user_id)
        if not cats:
            return
        mes_actual = datetime.now().replace(day=1).date().isoformat()
        try:
            res = supabase.table("presupuestos").select("*").eq("mes", mes_actual).eq("user_id", user_id).execute()
            presupuestos_dict = {p["categoria_id"]: p["monto_limite"] for p in res.data}
        except:
            presupuestos_dict = {}
        for cat in cats:
            cat_id = cat["id"]
            try:
                gastos_res = supabase.table("gastos").select("monto").eq("categoria_id", cat_id).eq("user_id", user_id)\
                    .gte("created_at", f"{mes_actual}T00:00:00").lt("created_at", f"{mes_actual}T00:00:00 + 1 month").execute()
                gastado = sum(g["monto"] for g in gastos_res.data) if gastos_res.data else 0
            except:
                gastado = 0
            limite = presupuestos_dict.get(cat_id, 0)
            progress = gastado / limite if limite > 0 else 0
            emoji = cat.get("icono", "")
            row = ft.Container(
                bgcolor=colors["surface"],
                border_radius=16,
                padding=10,
                content=ft.Column([
                    ft.Row([
                        ft.Text(f"{emoji} ", size=18),
                        ft.Text(cat["nombre"], size=16, weight="bold", expand=True, color=colors["text"]),
                        ft.Text(f"{format_currency(gastado, currency)} / {format_currency(limite, currency)}",
                                size=14, color=colors["success"] if gastado <= limite else colors["error"]),
                    ]),
                    ft.ProgressBar(value=min(progress, 1.0), width=400,
                                   color=colors["primary"] if progress <= 1 else colors["error"], bgcolor="#333333"),
                    ft.Row([ft.TextButton("Editar", on_click=lambda e, cid=cat_id, lim=limite: abrir_editor_presupuesto(cid, lim))],
                           alignment=ft.MainAxisAlignment.END),
                ])
            )
            presupuestos_grid.controls.append(row)
        page.update()

    def abrir_editor_presupuesto(categoria_id, limite_actual):
        input_limite = ft.TextField(label="Monto límite mensual", value=str(limite_actual) if limite_actual else "",
                                    prefix=ft.Text(currency_symbol), width=200)
        def guardar(e):
            try:
                nuevo_limite = float(input_limite.value)
            except:
                mostrar_snackbar(page, "Ingresa un número válido", colors["error"])
                return
            if nuevo_limite <= 0:
                mostrar_snackbar(page, "El monto debe ser mayor a 0", colors["error"])
                return
            mes_actual = datetime.now().replace(day=1).date().isoformat()
            try:
                supabase.table("presupuestos").upsert({
                    "categoria_id": categoria_id,
                    "monto_limite": nuevo_limite,
                    "mes": mes_actual,
                    "user_id": user_id
                }, on_conflict="categoria_id,mes,user_id").execute()
                mostrar_snackbar(page, "Presupuesto actualizado", colors["success"])
                cargar_presupuestos()
                close_dialog(page, dlg)
                page.update()
            except Exception as ex:
                mostrar_snackbar(page, f"Error: {ex}", colors["error"])
        dlg = ft.AlertDialog(
            title=ft.Text("Editar presupuesto"),
            content=input_limite,
            actions=[ft.TextButton("Guardar", on_click=guardar), ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    # ==================== DASHBOARD ====================
    def cargar_dashboard():
        dashboard_grid.controls.clear()
        gastos = cargar_gastos_con_categoria(user_id)
        hoy = datetime.now().date()
        mes_date = hoy.replace(day=1)
        mes_str = mes_date.isoformat()

        gastos_mes = [g for g in gastos if g.get("created_at", "").startswith(mes_str)]
        total_gastado = sum(g["monto"] for g in gastos_mes)

        try:
            res = supabase.table("presupuestos").select("*, categorias(nombre, icono)").eq("mes", mes_str).eq("user_id", user_id).execute()
            presupuestos = res.data if res.data else []
        except:
            presupuestos = []
        total_presupuestado = sum(p["monto_limite"] for p in presupuestos)

        if mes_date.month == 12:
            siguiente_mes = mes_date.replace(year=mes_date.year + 1, month=1)
        else:
            siguiente_mes = mes_date.replace(month=mes_date.month + 1)
        dias_totales = (siguiente_mes - mes_date).days
        dia_actual = min((hoy - mes_date).days + 1, dias_totales)
        gasto_promedio_diario = total_gastado / dia_actual if dia_actual > 0 else 0

        gastos_por_cat = defaultdict(float)
        iconos_por_cat = {}
        for g in gastos_mes:
            cat = g.get("categorias", {})
            nombre = cat.get("nombre", "Sin categoría") if isinstance(cat, dict) else "Sin categoría"
            icono = cat.get("icono", "") if isinstance(cat, dict) else ""
            gastos_por_cat[nombre] += g.get("monto", 0)
            iconos_por_cat[nombre] = icono
        cat_top = max(gastos_por_cat.items(), key=lambda x: x[1]) if gastos_por_cat else ("Ninguna", 0)

        progress = total_gastado / total_presupuestado if total_presupuestado > 0 else 0
        saldo = total_presupuestado - total_gastado

        dashboard_grid.controls.append(
            ft.Container(
                bgcolor=colors["surface"], border_radius=16, padding=15,
                content=ft.Column([
                    ft.Text("📌 Consejo del día", size=14, weight="bold", color=colors["primary"]),
                    ft.Text(consejo_del_dia(), size=13, color=colors["text"], italic=True),
                ])
            )
        )

        try:
            racha_res = supabase.table("rachas").select("racha_actual").eq("user_id", user_id).execute()
            racha_hoy = racha_res.data[0]["racha_actual"] if racha_res.data else 0
        except:
            racha_hoy = 0
        dashboard_grid.controls.append(
            ft.Container(
                bgcolor=colors["surface"], border_radius=16, padding=20,
                content=ft.Column([
                    ft.Text("🔥 Racha actual", size=14, color=colors["text_secondary"]),
                    ft.Text(f"{racha_hoy} días", size=28, weight="bold", color=colors["primary"]),
                    ft.Text("¡Sigue registrando gastos!", size=12, color=colors["text_secondary"]),
                ])
            )
        )

        dashboard_grid.controls.append(
            ft.Container(
                bgcolor=colors["surface"], border_radius=16, padding=20,
                content=ft.Column([
                    ft.Text("💰 Gasto Total del Mes", size=14, color=colors["text_secondary"]),
                    ft.Text(format_currency(total_gastado, currency), size=28, weight="bold", color=colors["text"]),
                    ft.ProgressBar(value=min(progress, 1.0), color=colors["primary"] if progress <= 1 else colors["error"], bgcolor="#333333"),
                    ft.Text(f"{progress*100:.1f}% del presupuesto", size=12, color=colors["text_secondary"]),
                ])
            )
        )

        color_saldo = colors["success"] if saldo >= 0 else colors["error"]
        dashboard_grid.controls.append(
            ft.Container(
                bgcolor=colors["surface"], border_radius=16, padding=20,
                content=ft.Column([
                    ft.Text("💵 Saldo Restante", size=14, color=colors["text_secondary"]),
                    ft.Text(format_currency(saldo, currency), size=28, weight="bold", color=color_saldo),
                    ft.Text(f"Presupuesto: {format_currency(total_presupuestado, currency)}", size=12, color=colors["text_secondary"]),
                ])
            )
        )

        dashboard_grid.controls.append(
            ft.Container(
                bgcolor=colors["surface"], border_radius=16, padding=20,
                content=ft.Column([
                    ft.Text("📊 Gasto Promedio Diario", size=14, color=colors["text_secondary"]),
                    ft.Text(format_currency(gasto_promedio_diario, currency), size=28, weight="bold", color=colors["text"]),
                    ft.Text(f"Día {dia_actual} de {dias_totales}", size=12, color=colors["text_secondary"]),
                ])
            )
        )

        icono_top = iconos_por_cat.get(cat_top[0], "")
        dashboard_grid.controls.append(
            ft.Container(
                bgcolor=colors["surface"], border_radius=16, padding=20,
                content=ft.Column([
                    ft.Text("🔥 Mayor Gasto", size=14, color=colors["text_secondary"]),
                    ft.Row([
                        ft.Text(f"{icono_top} ", size=24),
                        ft.Text(cat_top[0], size=18, weight="bold", color=colors["text"]),
                    ]),
                    ft.Text(format_currency(cat_top[1], currency), size=22, color=colors["error"]),
                ])
            )
        )

        page.update()

    # ==================== ACTUALIZACIÓN DE VISTAS ====================
    def actualizar_graficos(datos):
        img_pie = generar_grafico_gastos(datos, page.theme_mode)
        if img_pie:
            grafico_container.content = img_pie
            grafico_container.visible = True
        else:
            grafico_container.visible = False
        img_trend = generar_grafico_tendencia(datos, page.theme_mode)
        if img_trend:
            tendencia_container.content = img_trend
            tendencia_container.visible = True
        else:
            tendencia_container.visible = False
        page.update()

    def actualizar_lista_visual():
        contenedor_historial.controls.clear()
        gastos = cargar_gastos_con_categoria(user_id)
        actualizar_graficos(gastos)

        hoy = datetime.now().strftime("%Y-%m-%d")
        gastos_hoy = [g for g in gastos if g.get("created_at", "").startswith(hoy)]

        if not gastos:
            contenedor_historial.controls.append(
                ft.Container(
                    content=ft.Text("📭 No hay gastos registrados", italic=True, opacity=0.6),
                    alignment=ft.Alignment.CENTER,
                    padding=30
                )
            )
        else:
            if not gastos_hoy and recordatorios_activos:
                contenedor_historial.controls.append(
                    ft.Container(
                        bgcolor=colors["surface"],
                        border_radius=12,
                        padding=10,
                        content=ft.Row([
                            ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE, color=colors["secondary"], size=20),
                            ft.Text("⚠️ No has registrado gastos hoy. ¡Recuerda anotarlos!", size=14, color=colors["secondary"]),
                        ])
                    )
                )
            for gasto in reversed(gastos):
                cat_info = gasto.get("categorias")
                if isinstance(cat_info, dict):
                    nombre_cat = cat_info.get("nombre", "Sin categoría")
                    icono_cat = cat_info.get("icono", "")
                elif isinstance(cat_info, list) and len(cat_info) > 0:
                    nombre_cat = cat_info[0].get("nombre", "Sin categoría")
                    icono_cat = cat_info[0].get("icono", "")
                else:
                    nombre_cat = "Sin categoría"
                    icono_cat = ""
                monto = gasto.get('monto', 0)
                card = ft.Container(
                    bgcolor=colors["surface"], border_radius=16, padding=12, margin=ft.Margin.only(bottom=8),
                    shadow=ft.BoxShadow(spread_radius=1, blur_radius=8, color=ft.Colors.TRANSPARENT, offset=ft.Offset(0, 2)),
                    content=ft.Row([
                        ft.Text(f"{icono_cat} ", size=20),
                        ft.Column([
                            ft.Text(gasto.get("nombre", "Sin nombre"), size=15, weight="bold", color=colors["text"]),
                            ft.Text(nombre_cat, size=12, color=colors["text_secondary"]),
                        ], spacing=0),
                        ft.Text(format_currency(monto, currency), size=16, weight="bold", color=colors["success"],
                                expand=True, text_align="right"),
                    ])
                )
                contenedor_historial.controls.append(card)
        page.update()

    def guardar_gasto_nube(e):
        nombre = input_nombre.value.strip()
        monto_str = input_monto.value.strip()
        categoria_id = int(categoria_dropdown.value) if categoria_dropdown.value else None
        if not nombre or not monto_str or not categoria_id:
            mostrar_snackbar(page, "❌ Completa todos los campos (incluye categoría)", colors["error"])
            return
        try:
            monto_val = float(monto_str)
            supabase.table("gastos").insert({
                "nombre": nombre,
                "monto": monto_val,
                "categoria_id": categoria_id,
                "user_id": user_id
            }).execute()
            input_nombre.value = ""
            input_monto.value = ""
            actualizar_lista_visual()
            if vista_presupuestos.visible:
                cargar_presupuestos()
            if vista_dashboard.visible:
                cargar_dashboard()
            actualizar_racha()
            verificar_alertas_presupuesto()
            mostrar_snackbar(page, "✅ Gasto guardado", colors["success"])
        except ValueError:
            mostrar_snackbar(page, "❌ Monto inválido", colors["error"])
        except Exception as ex:
            print(ex)
            mostrar_snackbar(page, "❌ Error al guardar", colors["error"])

    # ==================== IA GURU ====================
    def consultar_guru(e):
        if not GENAI_OK:
            mostrar_snackbar(page, "⚠️ La IA Guru no está disponible", colors["error"])
            return
        if not premium:
            mostrar_snackbar(page, "⚠️ IA Guru es Premium", colors["error"])
            return
        if not input_chat.value:
            return
        pregunta = input_chat.value
        chat_display.controls.append(ft.Text(f"👤 Tú: {pregunta}", color=colors["secondary"], weight="bold"))
        input_chat.value = ""
        page.update()
        thinking = ft.Text("🧙 Guru: Pensando...", italic=True, color=colors["text_secondary"])
        chat_display.controls.append(thinking)
        page.update()
        if not client:
            respuesta = "No se ha configurado una API Key de Gemini."
        else:
            gastos = cargar_gastos_con_categoria(user_id)
            total = sum(g.get("monto", 0) for g in gastos)
            contexto = f"Total gastado: {format_currency(total, currency)}. Últimos gastos: " + ", ".join(
                [f"{g.get('nombre','')} {format_currency(g.get('monto',0), currency)}" for g in gastos[-3:]])
            prompt = f"Eres un asesor financiero. Contexto: {contexto}. Pregunta: {pregunta}"
            try:
                resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                respuesta = resp.text
            except Exception as ex:
                respuesta = f"Error en Gemini: {str(ex)[:150]}"
        chat_display.controls.remove(thinking)
        chat_display.controls.append(ft.Container(content=ft.Markdown(f"🧙 **Guru:** {respuesta}"), padding=12,
                                                  bgcolor=colors["surface"], border_radius=16))
        page.update()

    # ==================== CIERRE DE SESIÓN Y TEMA ====================
    def logout(e):
        supabase.auth.sign_out()
        page.user_id = None
        page.user_email = None
        login_view(page)

    def cambiar_tema(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            nuevo = ft.ThemeMode.LIGHT
            guardar = "LIGHT"
        elif page.theme_mode == ft.ThemeMode.LIGHT:
            nuevo = ft.ThemeMode.SYSTEM
            guardar = "SYSTEM"
        else:
            nuevo = ft.ThemeMode.DARK
            guardar = "DARK"
        page.theme_mode = nuevo
        if hasattr(page, "client_storage"):
            page.client_storage.set("theme_mode", guardar)
        page.clean()
        main_app(page)

    # ==================== CONFIGURACIÓN ====================
    def abrir_configuracion(e):
        currency_dd = ft.Dropdown(
            label="Moneda",
            options=[
                ft.dropdown.Option("CRC", "Colón costarricense (₡)"),
                ft.dropdown.Option("USD", "Dólar estadounidense ($)"),
                ft.dropdown.Option("COP", "Peso colombiano ($)"),
                ft.dropdown.Option("EUR", "Euro (€)"),
                ft.dropdown.Option("MXN", "Peso mexicano ($)"),
            ],
            value=currency,
        )
        tema_dd = ft.Dropdown(
            label="Tema",
            options=[
                ft.dropdown.Option("DARK", "Oscuro"),
                ft.dropdown.Option("LIGHT", "Claro"),
                ft.dropdown.Option("SYSTEM", "Automático"),
            ],
            value="DARK" if page.theme_mode == ft.ThemeMode.DARK else ("LIGHT" if page.theme_mode == ft.ThemeMode.LIGHT else "SYSTEM"),
        )
        recordatorios_switch = ft.Switch(
            label="Recordatorios diarios",
            value=recordatorios_activos,
        )

        def guardar_config():
            nueva_moneda = currency_dd.value
            if hasattr(page, "client_storage"):
                page.client_storage.set("currency", nueva_moneda)
                page.client_storage.set("recordatorios", "true" if recordatorios_switch.value else "false")
                page.client_storage.set("theme_mode", tema_dd.value)
            close_dialog(page, dlg)
            mostrar_snackbar(page, "Configuración guardada. Reiniciando...", colors["success"])
            page.clean()
            main_app(page)

        dlg = ft.AlertDialog(
            title=ft.Text("Configuración"),
            content=ft.Column([tema_dd, currency_dd, ft.Divider(), recordatorios_switch]),
            actions=[
                ft.TextButton("Guardar", on_click=lambda e: guardar_config()),
                ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    # ==================== GESTIÓN DE CATEGORÍAS ====================
    def abrir_gestor_categorias(e):
        cats = cargar_categorias(user_id)
        lista_categorias = ft.Column(spacing=8, scroll=ft.ScrollMode.ALWAYS, expand=True)
        def refrescar_lista():
            nonlocal cats
            cats = cargar_categorias(user_id)
            lista_categorias.controls.clear()
            for c in cats:
                emoji = c.get("icono", "")
                nombre = c["nombre"]
                cid = c["id"]
                es_global = c["user_id"] == "00000000-0000-0000-0000-000000000001"
                fila = ft.Row([
                    ft.Text(f"{emoji}  {nombre}", expand=True),
                    ft.IconButton(ft.Icons.EDIT, icon_size=18, on_click=lambda e, cid=cid, nombre=nombre, emoji=emoji: editar_cat(cid, nombre, emoji)),
                    ft.IconButton(ft.Icons.DELETE, icon_size=18, icon_color="red", on_click=lambda e, cid=cid, nombre=nombre: confirmar_eliminar(cid, nombre))
                ])
                if es_global:
                    fila.controls[-1].disabled = True
                lista_categorias.controls.append(fila)
            page.update()
        def agregar_nueva():
            nombre = nuevo_nombre.value.strip()
            emoji = nuevo_emoji.value if hasattr(nuevo_emoji, 'value') else "📦"
            if not nombre:
                mostrar_snackbar(page, "Ingresa un nombre", colors["error"])
                return
            agregar_categoria(nombre, emoji, user_id)
            nuevo_nombre.value = ""
            refrescar_lista()
            mostrar_snackbar(page, "Categoría agregada", colors["success"])
        def editar_cat(cid, nombre_actual, emoji_actual):
            edit_nombre = ft.TextField(label="Nuevo nombre", value=nombre_actual)
            edit_emoji = ft.TextField(label="Emoji", value=emoji_actual)
            def guardar_edicion():
                nuevo_n = edit_nombre.value.strip()
                nuevo_e = edit_emoji.value.strip() or "📦"
                if not nuevo_n:
                    return
                editar_categoria(cid, nuevo_n, nuevo_e)
                close_dialog(page, dlg_edit)
                refrescar_lista()
                mostrar_snackbar(page, "Categoría actualizada", colors["success"])
            dlg_edit = ft.AlertDialog(
                title=ft.Text("Editar categoría"),
                content=ft.Column([edit_nombre, edit_emoji]),
                actions=[ft.TextButton("Guardar", on_click=lambda e: guardar_edicion()), ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg_edit))]
            )
            page.show_dialog(dlg_edit)
        def confirmar_eliminar(cid, nombre):
            def eliminar():
                eliminar_categoria(cid)
                close_dialog(page, dlg_confirm)
                refrescar_lista()
                mostrar_snackbar(page, f"Categoría '{nombre}' eliminada", colors["success"])
            dlg_confirm = ft.AlertDialog(
                title=ft.Text("Eliminar categoría"),
                content=ft.Text(f"¿Seguro que deseas eliminar '{nombre}'?"),
                actions=[ft.TextButton("Eliminar", on_click=lambda e: eliminar()), ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page, dlg_confirm))]
            )
            page.show_dialog(dlg_confirm)
        nuevo_nombre = ft.TextField(label="Nombre de nueva categoría", expand=True)
        nuevo_emoji = ft.TextField(label="Emoji (ej. 🍕)", width=80, value="📦")
        def seleccionar_emoji(e):
            nuevo_emoji.value = e.control.data
            page.update()
        emoji_grid = ft.Row(
            [ft.TextButton(emoji, data=emoji, on_click=seleccionar_emoji) for emoji in EMOJI_LIST],
            wrap=True, spacing=2
        )
        dlg = ft.AlertDialog(
            title=ft.Text("🏷️ Gestionar Categorías"),
            content=ft.Column([
                ft.Text("Categorías actuales:", weight="bold"),
                ft.Container(content=lista_categorias, height=200, border_radius=10, bgcolor=colors["surface"], padding=10),
                ft.Divider(),
                ft.Text("Nueva categoría:", weight="bold"),
                ft.Row([nuevo_nombre, nuevo_emoji, ft.IconButton(ft.Icons.ADD, on_click=lambda e: agregar_nueva())]),
                ft.Text("Selecciona un emoji:", size=12),
                emoji_grid,
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: close_dialog(page, dlg))]
        )
        refrescar_lista()
        page.show_dialog(dlg)

    # ==================== GESTIÓN DE RECORDATORIOS ====================
    def cargar_recordatorios():
        try:
            res = supabase.table("recordatorios").select("*").eq("user_id", user_id).order("fecha_inicio").execute()
            return res.data if res.data else []
        except:
            return []

    def abrir_gestor_recordatorios(e):
        recs = cargar_recordatorios()
        lista = ft.Column(spacing=8)
        def refrescar():
            nonlocal recs
            recs = cargar_recordatorios()
            lista.controls.clear()
            for r in recs:
                estado = "🟢" if r["activo"] else "🔴"
                lista.controls.append(
                    ft.Row([
                        ft.Text(f"{estado} {r['titulo']} ({r['frecuencia']}) - {r['fecha_inicio']}"),
                        ft.IconButton(ft.Icons.DELETE, icon_size=18, icon_color="red", on_click=lambda e, rid=r["id"]: eliminar_recordatorio(rid))
                    ])
                )
            page.update()

        def eliminar_recordatorio(rid):
            supabase.table("recordatorios").delete().eq("id", rid).execute()
            refrescar()

        titulo = ft.TextField(label="Título", expand=True)
        monto = ft.TextField(label="Monto", prefix=ft.Text(currency_symbol))
        fecha = ft.TextField(label="Fecha inicio (YYYY-MM-DD)", hint_text="2025-05-25")
        frecuencia = ft.Dropdown(
            label="Frecuencia",
            options=[
                ft.dropdown.Option("unico", "Único"),
                ft.dropdown.Option("semanal", "Semanal"),
                ft.dropdown.Option("mensual", "Mensual"),
                ft.dropdown.Option("anual", "Anual"),
            ],
            value="mensual"
        )
        def agregar():
            try:
                monto_val = float(monto.value) if monto.value else None
                supabase.table("recordatorios").insert({
                    "user_id": user_id,
                    "titulo": titulo.value,
                    "monto": monto_val,
                    "fecha_inicio": fecha.value,
                    "frecuencia": frecuencia.value,
                    "activo": True
                }).execute()
                titulo.value, monto.value, fecha.value = "", "", ""
                refrescar()
            except Exception as ex:
                mostrar_snackbar(page, f"Error: {ex}", colors["error"])

        dlg = ft.AlertDialog(
            title=ft.Text("🔔 Recordatorios personalizados"),
            content=ft.Column([
                ft.Text("Tus recordatorios:"),
                ft.Container(content=lista, height=150, bgcolor=colors["surface"], padding=10, border_radius=10),
                ft.Divider(),
                titulo, monto, fecha, frecuencia,
                ft.FilledButton("Agregar", on_click=lambda e: agregar())
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: close_dialog(page, dlg))]
        )
        refrescar()
        page.show_dialog(dlg)

    # ==================== MENÚ DE OPCIONES ====================
    def popup_acciones():
        return ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Opciones",
            items=[
                ft.PopupMenuItem(content=ft.Text("📦 Exportar Backup"), icon=ft.Icons.BACKUP, on_click=exportar_backup),
                ft.PopupMenuItem(content=ft.Text("📥 Importar Backup"), icon=ft.Icons.UPLOAD_FILE, on_click=importar_backup),
                ft.PopupMenuItem(content=ft.Text("📲 Leer SMS"), icon=ft.Icons.SMS, on_click=importar_sms),
                ft.PopupMenuItem(content=ft.Text("Exportar CSV"), icon=ft.Icons.DOWNLOAD, on_click=exportar_csv),
                ft.PopupMenuItem(content=ft.Text("Exportar Excel"), icon=ft.Icons.TABLE_CHART, on_click=exportar_excel),
                ft.PopupMenuItem(content=ft.Text("Exportar PDF"), icon=ft.Icons.PICTURE_AS_PDF, on_click=exportar_pdf),
                ft.PopupMenuItem(content=ft.Text("Cambiar tema"), icon=ft.Icons.BRIGHTNESS_4, on_click=cambiar_tema),
                ft.PopupMenuItem(content=ft.Text("🔄 Sincronizar ahora"), icon=ft.Icons.SYNC, on_click=lambda e: sincronizar_datos()),
                ft.PopupMenuItem(content=ft.Text("⚙️ Configuración"), icon=ft.Icons.SETTINGS, on_click=lambda e: abrir_configuracion(e)),
                ft.PopupMenuItem(content=ft.Text("🏷️ Categorías"), icon=ft.Icons.CATEGORY, on_click=abrir_gestor_categorias),
                ft.PopupMenuItem(content=ft.Text("🔔 Recordatorios"), icon=ft.Icons.NOTIFICATIONS, on_click=abrir_gestor_recordatorios),
                ft.PopupMenuItem(content=ft.Text("🔑 Cambiar PIN"), icon=ft.Icons.LOCK, on_click=lambda e: cambiar_pin(page)),
                ft.PopupMenuItem(content=ft.Text("Cerrar sesión"), icon=ft.Icons.LOGOUT, on_click=logout),
            ],
        )

    # ==================== VISTAS ====================
    vista_gastos = ft.Column([
        ft.Row([ft.Text("MoneyFlow", size=24, weight="bold", color=colors["primary"]), popup_acciones()],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([ft.Text(f"Bienvenido, {user_email}", size=12, color=colors["text_secondary"]), estado_conexion],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
        ft.Column([input_nombre, ft.Row([input_monto, categoria_dropdown], spacing=10)], spacing=10),
        ft.FilledButton("Añadir Gasto", on_click=guardar_gasto_nube, icon=ft.Icons.ADD_CIRCLE, expand=True,
                        style=ft.ButtonStyle(bgcolor=colors["primary"], color=colors["bg"], shape=ft.RoundedRectangleBorder(radius=30))),
        ft.Divider(height=16),
        grafico_container,
        ft.Text("Distribución por gastos", size=12, weight="bold", color=colors["text_secondary"]),
        tendencia_container,
        ft.Text("Evolución mensual", size=12, weight="bold", color=colors["text_secondary"]),
        ft.Divider(height=8),
        ft.Text("Historial", size=16, weight="bold", color=colors["text"]),
        ft.Container(content=contenedor_historial, expand=True, bgcolor=ft.Colors.TRANSPARENT, border_radius=16)
    ], visible=False, expand=True, scroll=ft.ScrollMode.AUTO)

    vista_presupuestos = ft.Column([
        ft.Row([ft.Text("Presupuestos Mensuales", size=22, weight="bold", color=colors["primary"]), popup_acciones()],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([ft.Text(f"Bienvenido, {user_email}", size=12, color=colors["text_secondary"]), estado_conexion],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
        presupuestos_grid
    ], visible=False, expand=True, scroll=ft.ScrollMode.AUTO)

    vista_dashboard = ft.Column([
        ft.Row([ft.Text("📈 Dashboard", size=24, weight="bold", color=colors["primary"]), popup_acciones()],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([ft.Text(f"Resumen del mes - {user_email}", size=12, color=colors["text_secondary"]), estado_conexion],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
        dashboard_grid
    ], visible=False, expand=True, scroll=ft.ScrollMode.AUTO)

    vista_ia = ft.Column([
        ft.Row([ft.Text("Money-Guru AI", size=24, weight="bold", color=colors["primary"]), popup_acciones()],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([ft.Text(f"Bienvenido, {user_email}", size=12, color=colors["text_secondary"]), estado_conexion],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
        ft.Container(content=chat_display, expand=True, bgcolor=colors["surface"], border_radius=16, padding=10),
        ft.Row([input_chat, ft.IconButton(ft.Icons.SEND, on_click=consultar_guru, icon_color=colors["primary"])], spacing=5)
    ], visible=False, expand=True)

    vista_perfil = ft.Column([
        ft.Row([ft.Text("👤 Perfil", size=24, weight="bold", color=colors["primary"]), popup_acciones()],
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
        perfil_contenido
    ], visible=False, expand=True, scroll=ft.ScrollMode.AUTO)

    # ==================== NAVEGACIÓN INFERIOR (5 vistas) ====================
    def cambiar_vista(e):
        indice = e.control.selected_index
        vista_gastos.visible = (indice == 0)
        vista_presupuestos.visible = (indice == 1)
        vista_dashboard.visible = (indice == 2)
        vista_ia.visible = (indice == 3)
        vista_perfil.visible = (indice == 4)
        if indice == 1:
            cargar_presupuestos()
        elif indice == 2:
            cargar_dashboard()
        elif indice == 4:
            cargar_perfil()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=cambiar_vista,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ATTACH_MONEY, label="GASTOS"),
            ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART, label="PRESUP."),
            ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD, label="DASHBOARD"),
            ft.NavigationBarDestination(icon=ft.Icons.PSYCHOLOGY, label="IA"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON, label="PERFIL"),
        ],
        bgcolor=colors["surface"],
    )

    page.add(
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        vista_gastos,
        vista_presupuestos,
        vista_dashboard,
        vista_ia,
        vista_perfil
    )
    vista_gastos.visible = True
    actualizar_lista_visual()
    sincronizar_datos(silencioso=True)
    actualizar_estado_conexion()   # Forzar actualización visual tras la primera sincronización

    cancelar_monitoreo = iniciar_monitoreo_conexion(page, estado_conexion, online, sincronizando, sincronizar_datos)

    scheduler = BackgroundScheduler(timezone=pytz.timezone("America/Costa_Rica"))
    scheduler.add_job(job_revisar, 'interval', minutes=30, id='recordatorios_job')
    scheduler.start()

    def on_close(e):
        scheduler.shutdown(wait=False)
        cancelar_monitoreo()
        page.window_destroy()
    page.on_window_destroy = on_close

    page.update()

# ==================== PUNTO DE ENTRADA ====================
def main(page: ft.Page):
    try:
        page.title = "MoneyFlow Cloud AI"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 20

        if not verificar_y_guia_configuracion(page):
            page.add(ft.Text("Configuración pendiente", color=AppColors.DARK["error"]))
            return

        try:
            if hasattr(page, "client_storage"):
                saved_theme = page.client_storage.get("theme_mode")
                if saved_theme == "LIGHT":
                    page.theme_mode = ft.ThemeMode.LIGHT
                elif saved_theme == "DARK":
                    page.theme_mode = ft.ThemeMode.DARK
                elif saved_theme == "SYSTEM":
                    page.theme_mode = ft.ThemeMode.SYSTEM
        except:
            pass

        page.bgcolor = AppColors.get(page.theme_mode)["bg"]

        if hasattr(page, "user_id") and page.user_id:
            solicitar_pin(page, lambda: main_app(page))
        else:
            login_view(page)

    except Exception as ex:
        import traceback
        error_msg = f"Error crítico:\n{str(ex)}\n\nDetalle:\n{traceback.format_exc()}"
        page.dialog = ft.AlertDialog(
            title=ft.Text("⚠️ Error"),
            content=ft.Text(error_msg, selectable=True, size=12),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: page.window_close())]
        )
        page.dialog.open = True
        page.update()

if __name__ == "__main__":
    ft.run(main)