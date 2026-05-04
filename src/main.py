import flet as ft
from supabase import create_client, Client
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIGURACIÓN DE CONEXIÓN ---
SUPABASE_URL = "https://xwvebpdivouldkvfrogh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh3dmVicGRpdm91bGRrdmZyb2doIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY2NTI1NTgsImV4cCI6MjA5MjIyODU1OH0.5eI8mdM3bR7SAPhqp0tcGPY02GUh3xuUQEvtRHNjU5s"
db: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class AppColors:
    PRIMARY = "#00d1ff"
    BG = "#0f172a"
    CARD = "#1e293b"
    TEXT = "#f8fafc"

def main(page: ft.Page):
    page.title = "MoneyFlow"
    page.bgcolor = AppColors.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 450
    page.window.height = 800

    # --- FUNCIONES DE LÓGICA ---
    def actualizar_lista_gastos():
        lista_gastos_view.controls.clear()
        try:
            default_user_id = "00000000-0000-0000-0000-000000000001"
            res = db.table("gastos").select("*").eq("user_id", default_user_id).order("created_at", desc=True).execute()
            for item in res.data:
                lista_gastos_view.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Text("💰", size=20),
                            ft.Text(item.get('nombre', 'Sin concepto'), expand=True, color=AppColors.TEXT),
                            ft.Text(f"${item.get('monto', 0):.2f}", color=AppColors.PRIMARY),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=10,
                        bgcolor=AppColors.CARD,
                        border_radius=8,
                        margin=5,
                    )
                )
        except Exception as e:
            print(f"Error al cargar gastos: {e}")
        page.update()

    def agregar_gasto_db(e):
        if input_nombre.value and input_monto.value:
            try:
                default_user_id = "00000000-0000-0000-0000-000000000001"
                db.table("gastos").insert({
                    "nombre": input_nombre.value, 
                    "monto": float(input_monto.value),
                    "user_id": default_user_id
                }).execute()
                input_nombre.value = ""
                input_monto.value = ""
                actualizar_lista_gastos()
            except Exception as ex:
                print(f"Error al insertar: {ex}")

    # --- CONTROLES DE INTERFAZ ---
    input_nombre = ft.TextField(label="Concepto", expand=2, border_color=AppColors.PRIMARY, color=AppColors.TEXT)
    input_monto = ft.TextField(label="Monto", expand=1, border_color=AppColors.PRIMARY, color=AppColors.TEXT)
    lista_gastos_view = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=5)

    btn_add = ft.FilledButton(
        content=ft.Text("➕ Añadir Gasto", color=AppColors.BG),
        on_click=agregar_gasto_db,
        style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY)
    )

    # --- CONSTRUCCIÓN DE LA INTERFAZ ---
    page.add(
        ft.AppBar(
            title=ft.Text("MoneyFlow", color=AppColors.PRIMARY, weight="bold"), 
            bgcolor=AppColors.CARD
        ),
        ft.Container(
            content=ft.Column([
                ft.Text("Balance Actual", size=16, opacity=0.8, color=AppColors.TEXT),
                ft.Text("$0.00", size=32, weight="bold", color=AppColors.PRIMARY),
                ft.Divider(color=AppColors.PRIMARY),
                ft.Text("Registrar Gasto", weight="bold", color=AppColors.TEXT),
                ft.Row([input_nombre, input_monto, btn_add], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
            bgcolor=AppColors.BG,
            border_radius=15,
            expand=True
        )
    )

    actualizar_lista_gastos()

if __name__ == "__main__":
    ft.run(main)