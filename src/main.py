import flet as ft
import urllib.request
import urllib.error
import json
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIGURACIÓN DE SUPABASE ---
SUPABASE_URL = "https://xwvebpdivouldkvfrogh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh3dmVicGRpdm91bGRrdmZyb2doIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY2NTI1NTgsImV4cCI6MjA5MjIyODU1OH0.5eI8mdM3bR7SAPhqp0tcGPY02GUh3xuUQEvtRHNjU5s"

def hacer_peticion(url, metodo="GET", datos=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, headers=headers, method=metodo)
    if datos:
        req.data = json.dumps(datos).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error en peticion: {e}")
        return None

class AppColors:
    PRIMARY = "#00d1ff"
    BG = "#0f172a"
    CARD = "#1e293b"
    TEXT = "#f8fafc"

def main(page: ft.Page):
    page.title = "MoneyFlow"
    page.bgcolor = AppColors.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 450
    page.window_height = 800

    # --- CORRECCIÓN CRÍTICA: Registro de controles para evitar franjas rojas ---
    # Esto elimina el error "Unknown control: FilePicker"
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)
    page.update()

    def actualizar_lista_gastos():
        lista_gastos_view.controls.clear()
        try:
            url = f"{SUPABASE_URL}/rest/v1/gastos?select=*&user_id=eq.00000000-0000-0000-0000-000000000001&order=created_at.desc"
            gastos = hacer_peticion(url)
            total = 0
            if gastos:
                for item in gastos:
                    monto = item.get('monto', 0)
                    total += monto
                    lista_gastos_view.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Text("💰", size=20),
                                ft.Text(item.get('nombre', 'Sin concepto'), expand=True, color=AppColors.TEXT),
                                ft.Text(f"${monto:.2f}", color=AppColors.PRIMARY, weight="bold"),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            padding=10,
                            bgcolor=AppColors.CARD,
                            border_radius=8,
                            margin=5,
                        )
                    )
                text_balance.value = f"${total:.2f}"
            else:
                text_balance.value = "$0.00"
                lista_gastos_view.controls.append(
                    ft.Text("No hay gastos registrados", color=AppColors.TEXT, italic=True)
                )
        except Exception as e:
            print(f"Error al cargar: {e}")
        page.update()

    def agregar_gasto_db(e):
        if input_nombre.value and input_monto.value:
            try:
                data = {
                    "nombre": input_nombre.value,
                    "monto": float(input_monto.value),
                    "user_id": "00000000-0000-0000-0000-000000000001"
                }
                url = f"{SUPABASE_URL}/rest/v1/gastos"
                hacer_peticion(url, "POST", data)
                input_nombre.value = ""
                input_monto.value = ""
                actualizar_lista_gastos()
            except Exception as ex:
                print(f"Error al insertar: {ex}")

    # --- CONTROLES ---
    text_balance = ft.Text("$0.00", size=32, weight="bold", color=AppColors.PRIMARY)
    
    # CORRECCIÓN: Se usa 'hint_text' en lugar de 'placeholder'
    input_nombre = ft.TextField(label="Concepto", hint_text="¿En qué gastaste?", expand=2, border_color=AppColors.PRIMARY, color=AppColors.TEXT)
    input_monto = ft.TextField(label="Monto", hint_text="0.00", expand=1, border_color=AppColors.PRIMARY, color=AppColors.TEXT, keyboard_type=ft.KeyboardType.NUMBER)
    
    lista_gastos_view = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=5)

    # CORRECCIÓN: Botón con icono explícito para evitar franja roja derecha
    btn_add = ft.FilledButton(
        content=ft.Row([
            ft.Icon(ft.icons.ADD, color=AppColors.BG),
            ft.Text("Añadir Gasto", color=AppColors.BG)
        ], tight=True),
        on_click=agregar_gasto_db,
        style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY)
    )

    page.add(
        ft.AppBar(
            title=ft.Text("MoneyFlow", color=AppColors.PRIMARY, weight="bold"), 
            bgcolor=AppColors.CARD,
            center_title=True
        ),
        ft.Container(
            content=ft.Column([
                ft.Text("Balance Actual", size=16, opacity=0.8, color=AppColors.TEXT),
                text_balance,
                ft.Divider(color=AppColors.PRIMARY),
                ft.Text("Registrar Gasto", weight="bold", color=AppColors.TEXT),
                ft.Row([input_nombre, input_monto]),
                ft.Row([btn_add], alignment=ft.MainAxisAlignment.CENTER),
                ft.Divider(),
                ft.Text("Historial de Gastos", weight="bold", color=AppColors.TEXT),
                ft.Container(
                    content=lista_gastos_view, 
                    height=350,
                    bgcolor=AppColors.BG,
                    border_radius=10,
                    padding=5
                ),
            ]),
            padding=20,
            expand=True
        )
    )

    actualizar_lista_gastos()

if __name__ == "__main__":
    ft.run(main)