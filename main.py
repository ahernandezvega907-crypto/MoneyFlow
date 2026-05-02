import flet as ft
import os
import io
import sys
import base64
import csv
from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
from supabase import create_client, Client
from dotenv import load_dotenv
from google import genai

# Exportación avanzada
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors as reportlab_colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

load_dotenv()

# ==================== CONFIGURACIÓN ====================
SUPABASE_URL = "https://xwvebpdivouldkvfrogh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh3dmVicGRpdm91bGRrdmZyb2doIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY2NTI1NTgsImV4cCI6MjA5MjIyODU1OH0.5eI8mdM3bR7SAPhqp0tcGPY02GUh3xuUQEvtRHNjU5s"  # ⚠️ CAMBIA A TU CLAVE ANON
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except:
        pass

# ==================== FUNCIÓN PARA VERIFICAR LICENCIA PREMIUM ====================
def is_premium():
    """Verifica si existe el archivo de licencia 'license.key' en la misma carpeta del ejecutable o script."""
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

# ==================== FUNCIONES DE BASE DE DATOS ====================
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

def close_dialog(page):
    page.dialog.open = False
    page.update()

def cargar_categorias(user_id):
    try:
        res = supabase.table("categorias").select("id, nombre").eq("user_id", user_id).execute()
        if not res.data:
            default_cats = supabase.table("categorias").select("*").eq("user_id", "00000000-0000-0000-0000-000000000001").execute()
            for cat in default_cats.data:
                supabase.table("categorias").insert({
                    "nombre": cat["nombre"],
                    "icono": cat["icono"],
                    "user_id": user_id
                }).execute()
            res = supabase.table("categorias").select("id, nombre").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print("Error cargando categorías:", e)
        return []

def cargar_gastos_con_categoria(user_id):
    try:
        res = supabase.table("gastos").select("*, categorias(nombre)").order("created_at").eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print("Error cargando gastos:", e)
        return []

def generar_grafico_tendencia(datos, theme_mode):
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
    plt.ylabel("Gasto total ($)", fontsize=8, color=colors["text_secondary"])
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

# ==================== FUNCIÓN PARA GUARDAR ARCHIVOS LOCALMENTE ====================
def guardar_archivo_en_carpeta(page, nombre_archivo, contenido_bytes, subcarpeta="exportaciones", colors=None):
    """Guarda el archivo en una subcarpeta junto al ejecutable o script."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    export_dir = os.path.join(base_dir, subcarpeta)
    os.makedirs(export_dir, exist_ok=True)
    ruta_completa = os.path.join(export_dir, nombre_archivo)
    with open(ruta_completa, "wb") as f:
        f.write(contenido_bytes)
    msg = f"✓ Guardado en: {ruta_completa}"
    if colors:
        mostrar_snackbar(page, msg, colors["success"])
    else:
        mostrar_snackbar(page, msg, "#00C853")
    print(msg)

# ==================== PANTALLA DE LOGIN ====================
def login_view(page: ft.Page):
    page.clean()
    colors = AppColors.get(page.theme_mode)
    page.bgcolor = colors["bg"]
    page.padding = 20

    email_input = ft.TextField(label="Email", width=300, border_radius=16, bgcolor=colors["surface"], color=colors["text"])
    password_input = ft.TextField(label="Contraseña", password=True, width=300, border_radius=16, bgcolor=colors["surface"], color=colors["text"])
    error_text = ft.Text("", color=colors["error"])

    def do_login(e):
        try:
            res = supabase.auth.sign_in_with_password({"email": email_input.value, "password": password_input.value})
            page.user_id = res.user.id
            page.user_email = res.user.email
            main_app(page)
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
                ft.Text("MoneyFlow", size=40, weight="bold", color=colors["primary"]),
                ft.Text("Inicia sesión o regístrate", size=16, color=colors["text_secondary"]),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                email_input,
                password_input,
                ft.Row([
                    ft.Button("Iniciar sesión", on_click=do_login, style=ft.ButtonStyle(bgcolor=colors["primary"], color=colors["bg"])),
                    ft.Button("Registrarse", on_click=do_register, style=ft.ButtonStyle(bgcolor=colors["surface"], color=colors["text"])),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                error_text,
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
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

    # Determinar si el usuario es premium (existe license.key)
    premium = is_premium()

    # Tema guardado
    saved_theme = page.client_storage.get("theme_mode") if hasattr(page, "client_storage") else None
    if saved_theme == "LIGHT":
        page.theme_mode = ft.ThemeMode.LIGHT
    elif saved_theme == "DARK":
        page.theme_mode = ft.ThemeMode.DARK
    elif not hasattr(page, "theme_mode"):
        page.theme_mode = ft.ThemeMode.DARK

    colors = AppColors.get(page.theme_mode)
    page.bgcolor = colors["bg"]

    categorias = cargar_categorias(user_id)
    if not categorias:
        page.add(ft.Text("Error cargando categorías. Revisa conexión.", color=colors["error"]))
        return

    opciones_categorias = [ft.dropdown.Option(key=str(c["id"]), text=c["nombre"]) for c in categorias]

    input_nombre = ft.TextField(label="¿En qué gastaste?", expand=True, border_radius=16,
                                border_color=colors["text_secondary"], focused_border_color=colors["primary"],
                                bgcolor=colors["surface"], color=colors["text"])
    input_monto = ft.TextField(label="Monto", width=130, border_radius=16, border_color=colors["text_secondary"],
                               focused_border_color=colors["primary"], prefix=ft.Text("$ ", size=14),
                               bgcolor=colors["surface"], color=colors["text"])
    categoria_dropdown = ft.Dropdown(label="Categoría", width=150, options=opciones_categorias,
                                     value=opciones_categorias[0].key if opciones_categorias else None)

    contenedor_historial = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=12)
    chat_display = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=10)
    input_chat = ft.TextField(hint_text="Pregunta al Guru...", expand=True, border_radius=30,
                              border_color=colors["text_secondary"], focused_border_color=colors["primary"],
                              bgcolor=colors["surface"], color=colors["text"])
    grafico_container = ft.Container(visible=False, alignment=ft.Alignment.CENTER, padding=10)
    tendencia_container = ft.Container(visible=False, alignment=ft.Alignment.CENTER, padding=10)

    presupuestos_grid = ft.Column(spacing=15, scroll=ft.ScrollMode.ALWAYS)

    # ==================== FUNCIONES DE EXPORTACIÓN (con verificación premium) ====================
    def exportar_csv(e):
        # CSV es gratuito
        gastos = cargar_gastos_con_categoria(user_id)
        if not gastos:
            mostrar_snackbar(page, "No hay gastos para exportar", colors["error"])
            return
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Fecha", "Nombre", "Monto", "Categoría"])
        for g in gastos:
            categoria_nombre = g.get("categorias", {}).get("nombre") if isinstance(g.get("categorias"), dict) else ""
            fecha = g.get("created_at", datetime.now().isoformat())
            writer.writerow([fecha, g.get("nombre", ""), g.get("monto", 0), categoria_nombre])
        output.seek(0)
        data_bytes = output.getvalue().encode("utf-8")
        output.close()
        guardar_archivo_en_carpeta(page, "gastos.csv", data_bytes, colors=colors)

    def exportar_excel(e):
        print("DEBUG: exportar_excel llamado, premium =", premium)
        # Solo premium
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium. Adquiere tu licencia en nuestra web.", colors["error"])
            page.update()  # extra update
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
            categoria_nombre = g.get("categorias", {}).get("nombre") if isinstance(g.get("categorias"), dict) else ""
            fecha = g.get("created_at", datetime.now().isoformat())
            ws.append([fecha, g.get("nombre", ""), g.get("monto", 0), categoria_nombre])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        data_bytes = output.getvalue()
        output.close()
        guardar_archivo_en_carpeta(page, "gastos.xlsx", data_bytes, colors=colors)

    def exportar_pdf(e):
        print("DEBUG: exportar_pdf llamado, premium =", premium)
        # Solo premium
        if not premium:
            mostrar_snackbar(page, "❌ Función Premium. Adquiere tu licencia en nuestra web.", colors["error"])
            page.update()
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
        story.append(Spacer(1, 0.2*inch))

        data = [["Fecha", "Nombre", "Monto", "Categoría"]]
        total = 0
        for g in gastos:
            categoria_nombre = g.get("categorias", {}).get("nombre") if isinstance(g.get("categorias"), dict) else ""
            fecha = g.get("created_at", datetime.now().isoformat())[:10]
            monto = g.get("monto", 0)
            total += monto
            data.append([fecha, g.get("nombre", ""), f"${monto:.2f}", categoria_nombre])
        data.append(["", "", f"Total: ${total:.2f}", ""])

        table = Table(data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), reportlab_colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), reportlab_colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-2), reportlab_colors.beige),
            ('GRID', (0,0), (-1,-1), 1, reportlab_colors.black),
        ]))
        story.append(table)
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        guardar_archivo_en_carpeta(page, "gastos.pdf", pdf_bytes, colors=colors)

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
            row = ft.Container(
                bgcolor=colors["surface"],
                border_radius=16,
                padding=10,
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.CATEGORY, color=colors["primary"], size=20),
                        ft.Text(cat["nombre"], size=16, weight="bold", expand=True, color=colors["text"]),
                        ft.Text(f"${gastado:.2f}", size=14, color=colors["text_secondary"]),
                        ft.Text(f"/ ${limite:.2f}", size=14, color=colors["success"] if gastado <= limite else colors["error"]),
                    ]),
                    ft.ProgressBar(value=min(progress, 1.0), width=400,
                                   color=colors["primary"] if progress <= 1 else colors["error"], bgcolor="#333333"),
                    ft.Row([ft.TextButton("Editar presupuesto", on_click=lambda e, cid=cat_id, lim=limite: abrir_editor_presupuesto(cid, lim))],
                           alignment=ft.MainAxisAlignment.END),
                ])
            )
            presupuestos_grid.controls.append(row)
        page.update()

    def abrir_editor_presupuesto(categoria_id, limite_actual):
        input_limite = ft.TextField(label="Monto límite mensual", value=str(limite_actual) if limite_actual else "",
                                    prefix=ft.Text("$"), width=200)
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
                page.dialog.open = False
                page.update()
            except Exception as ex:
                mostrar_snackbar(page, f"Error: {ex}", colors["error"])

        page.dialog = ft.AlertDialog(
            title=ft.Text("Editar presupuesto", color=colors["text"]),
            content=input_limite,
            actions=[ft.TextButton("Guardar", on_click=guardar), ft.TextButton("Cancelar", on_click=lambda e: close_dialog(page))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.dialog.open = True
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
        if not gastos:
            contenedor_historial.controls.append(ft.Container(content=ft.Text("📭 No hay gastos registrados",
                                italic=True, opacity=0.6), alignment=ft.Alignment.CENTER, padding=30))
        else:
            for gasto in reversed(gastos):
                categoria_nombre = "Sin categoría"
                if gasto.get("categorias") and isinstance(gasto["categorias"], dict):
                    categoria_nombre = gasto["categorias"].get("nombre", "Sin categoría")
                elif isinstance(gasto.get("categorias"), list) and len(gasto["categorias"]) > 0:
                    categoria_nombre = gasto["categorias"][0].get("nombre", "Sin categoría")
                card = ft.Container(
                    bgcolor=colors["surface"], border_radius=16, padding=12, margin=ft.Margin.only(bottom=8),
                    shadow=ft.BoxShadow(spread_radius=1, blur_radius=8, color=ft.Colors.TRANSPARENT, offset=ft.Offset(0, 2)),
                    content=ft.Row([
                        ft.Icon(ft.Icons.ATTACH_MONEY, color=colors["primary"], size=22),
                        ft.Column([
                            ft.Text(gasto.get("nombre", "Sin nombre"), size=15, weight="bold", color=colors["text"]),
                            ft.Text(categoria_nombre, size=12, color=colors["text_secondary"]),
                        ], spacing=0),
                        ft.Text(f"${gasto.get('monto', 0):.2f}", size=16, weight="bold", color=colors["success"],
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
            mostrar_snackbar(page, "✅ Gasto guardado", colors["success"])
        except ValueError:
            mostrar_snackbar(page, "❌ Monto inválido", colors["error"])
        except Exception as ex:
            print(ex)
            mostrar_snackbar(page, "❌ Error al guardar", colors["error"])

    # ==================== IA GURU (solo premium) ====================
    def consultar_guru(e):
        print("DEBUG: consultar_guru llamado, premium =", premium)
        if not premium:
            mostrar_snackbar(page, "⚠️ La IA Guru es una función Premium. Adquiere tu licencia.", colors["error"])
            page.update()
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
            respuesta = "No se ha configurado una API Key de Gemini. Agrega GEMINI_API_KEY en el archivo .env"
        else:
            gastos = cargar_gastos_con_categoria(user_id)
            total = sum(g.get("monto", 0) for g in gastos)
            contexto = f"Total gastado: ${total:.2f}. Últimos gastos: " + ", ".join([f"{g.get('nombre','')} ${g.get('monto',0):.2f}" for g in gastos[-3:]])
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

    def toggle_theme(e):
        new_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        page.theme_mode = new_mode
        if hasattr(page, "client_storage"):
            page.client_storage.set("theme_mode", "LIGHT" if new_mode == ft.ThemeMode.LIGHT else "DARK")
        page.clean()
        main_app(page)

    # ==================== VISTAS ====================
    vista_gastos = ft.Column([
        ft.Row([
            ft.Text("MoneyFlow", size=32, weight="bold", color=colors["primary"]),
            ft.Row([
                ft.IconButton(ft.Icons.DOWNLOAD, on_click=exportar_csv, icon_color=colors["success"], tooltip="CSV"),
                ft.IconButton(ft.Icons.TABLE_CHART, on_click=exportar_excel, icon_color=colors["success"], tooltip="Excel"),
                ft.IconButton(ft.Icons.PICTURE_AS_PDF, on_click=exportar_pdf, icon_color=colors["success"], tooltip="PDF"),
                ft.IconButton(ft.Icons.BRIGHTNESS_4, on_click=toggle_theme, icon_color=colors["text"], tooltip="Cambiar tema"),
                ft.IconButton(ft.Icons.LOGOUT, on_click=logout, icon_color=colors["error"], tooltip="Cerrar sesión"),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text(f"Bienvenido, {user_email}", size=14, color=colors["text_secondary"]),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Row([input_nombre, input_monto, categoria_dropdown]),
        ft.FilledButton("Añadir Gasto", on_click=guardar_gasto_nube, icon=ft.Icons.ADD_CIRCLE, width=400,
                        style=ft.ButtonStyle(bgcolor=colors["primary"], color=colors["bg"], shape=ft.RoundedRectangleBorder(radius=30))),
        ft.Divider(height=20),
        grafico_container,
        ft.Divider(height=5),
        ft.Text("Distribución por gastos", size=14, weight="bold", color=colors["text_secondary"]),
        tendencia_container,
        ft.Text("Evolución mensual", size=14, weight="bold", color=colors["text_secondary"]),
        ft.Divider(height=10),
        ft.Text("Historial", size=18, weight="bold", color=colors["text"]),
        ft.Container(content=contenedor_historial, expand=True, bgcolor=ft.Colors.TRANSPARENT, border_radius=16)
    ], visible=True, expand=True, scroll=ft.ScrollMode.AUTO)

    vista_presupuestos = ft.Column([
        ft.Row([
            ft.Text("Presupuestos Mensuales", size=28, weight="bold", color=colors["primary"]),
            ft.Row([
                ft.IconButton(ft.Icons.DOWNLOAD, on_click=exportar_csv, icon_color=colors["success"], tooltip="CSV"),
                ft.IconButton(ft.Icons.TABLE_CHART, on_click=exportar_excel, icon_color=colors["success"], tooltip="Excel"),
                ft.IconButton(ft.Icons.PICTURE_AS_PDF, on_click=exportar_pdf, icon_color=colors["success"], tooltip="PDF"),
                ft.IconButton(ft.Icons.BRIGHTNESS_4, on_click=toggle_theme, icon_color=colors["text"], tooltip="Cambiar tema"),
                ft.IconButton(ft.Icons.LOGOUT, on_click=logout, icon_color=colors["error"], tooltip="Cerrar sesión"),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text(f"Bienvenido, {user_email}", size=14, color=colors["text_secondary"]),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        presupuestos_grid
    ], visible=False, expand=True, scroll=ft.ScrollMode.AUTO)

    vista_ia = ft.Column([
        ft.Row([
            ft.Text("Money-Guru AI", size=32, weight="bold", color=colors["primary"]),
            ft.Row([
                ft.IconButton(ft.Icons.DOWNLOAD, on_click=exportar_csv, icon_color=colors["success"], tooltip="CSV"),
                ft.IconButton(ft.Icons.TABLE_CHART, on_click=exportar_excel, icon_color=colors["success"], tooltip="Excel"),
                ft.IconButton(ft.Icons.PICTURE_AS_PDF, on_click=exportar_pdf, icon_color=colors["success"], tooltip="PDF"),
                ft.IconButton(ft.Icons.BRIGHTNESS_4, on_click=toggle_theme, icon_color=colors["text"], tooltip="Cambiar tema"),
                ft.IconButton(ft.Icons.LOGOUT, on_click=logout, icon_color=colors["error"], tooltip="Cerrar sesión"),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text(f"Bienvenido, {user_email}", size=14, color=colors["text_secondary"]),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Container(content=chat_display, expand=True, bgcolor=colors["surface"], border_radius=16, padding=10),
        ft.Row([input_chat, ft.IconButton(ft.Icons.SEND, on_click=consultar_guru, icon_color=colors["primary"],
                                          style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=30)))])
    ], visible=False, expand=True)

    def cambiar_vista(e):
        vista = e.control.data
        vista_gastos.visible = (vista == "GASTOS")
        vista_presupuestos.visible = (vista == "PRESUPUESTOS")
        vista_ia.visible = (vista == "IA GURU")
        btn_gastos.bgcolor = colors["primary"] if vista == "GASTOS" else colors["surface"]
        btn_presupuestos.bgcolor = colors["primary"] if vista == "PRESUPUESTOS" else colors["surface"]
        btn_ia.bgcolor = colors["primary"] if vista == "IA GURU" else colors["surface"]
        if vista == "PRESUPUESTOS":
            cargar_presupuestos()
        page.update()

    btn_gastos = ft.FilledButton("GASTOS", data="GASTOS", on_click=cambiar_vista,
                                 style=ft.ButtonStyle(bgcolor=colors["primary"], color=colors["bg"], shape=ft.RoundedRectangleBorder(radius=20)))
    btn_presupuestos = ft.FilledButton("PRESUPUESTOS", data="PRESUPUESTOS", on_click=cambiar_vista,
                                       style=ft.ButtonStyle(bgcolor=colors["surface"], color=colors["text"], shape=ft.RoundedRectangleBorder(radius=20)))
    btn_ia = ft.FilledButton("IA GURU", data="IA GURU", on_click=cambiar_vista,
                             style=ft.ButtonStyle(bgcolor=colors["surface"], color=colors["text"], shape=ft.RoundedRectangleBorder(radius=20)))

    page.add(
        ft.Row([btn_gastos, btn_presupuestos, btn_ia], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        vista_gastos,
        vista_presupuestos,
        vista_ia
    )
    actualizar_lista_visual()

# ==================== PUNTO DE ENTRADA ====================
def main(page: ft.Page):
    page.title = "MoneyFlow Cloud AI"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    if not verificar_y_guia_configuracion(page):
        page.add(ft.Text("Configuración pendiente", color=AppColors.DARK["error"]))
        return

    # Cargar tema guardado
    try:
        saved_theme = page.client_storage.get("theme_mode")
        if saved_theme == "LIGHT":
            page.theme_mode = ft.ThemeMode.LIGHT
        elif saved_theme == "DARK":
            page.theme_mode = ft.ThemeMode.DARK
    except:
        pass

    page.bgcolor = AppColors.get(page.theme_mode)["bg"]
    page.window.width = 500
    page.window.height = 750

    # Verificar si ya hay sesión activa
    if hasattr(page, "user_id") and page.user_id:
        main_app(page)
    else:
        login_view(page)

if __name__ == "__main__":
    ft.run(main)