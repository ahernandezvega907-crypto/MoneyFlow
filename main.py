import flet as ft
import os
import json # <--- Nuevo: para guardar datos
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def main(page: ft.Page):
    page.title = "MoneyFlow AI"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 450
    page.window_height = 700

    # --- LÓGICA DE PERSISTENCIA ---
    PATH_DATOS = "gastos.json"

    def cargar_datos():
        if os.path.exists(PATH_DATOS):
            try:
                with open(PATH_DATOS, "r") as f:
                    return json.load(f)
            except: return []
        return []

    def guardar_datos():
        with open(PATH_DATOS, "w") as f:
            json.dump(datos_gastos, f)

    # Cargamos los datos guardados al iniciar
    datos_gastos = cargar_datos()

    # --- ELEMENTOS DE INTERFAZ ---
    input_nombre = ft.TextField(label="Gasto", expand=True)
    input_monto = ft.TextField(label="Monto $", expand=True)
    lista_visual = ft.ListView(expand=True, spacing=10)
    chat_display = ft.Column(scroll=ft.ScrollMode.ALWAYS, height=350, expand=True)
    input_chat = ft.TextField(hint_text="Pregunta al Guru...", expand=True)

    def actualizar_lista_visual():
        lista_visual.controls.clear()
        for gasto in reversed(datos_gastos):
            lista_visual.controls.append(
                ft.ListTile(
                    title=ft.Text(gasto["nombre"]), 
                    subtitle=ft.Text(f"${gasto['monto']:.2f}"), 
                    leading=ft.Icon("attach_money")
                )
            )

    def agregar_gasto(e):
        try:
            monto = float(input_monto.value)
            datos_gastos.append({"nombre": input_nombre.value, "monto": monto})
            guardar_datos() # <--- Guardar en el archivo JSON
            actualizar_lista_visual()
            input_nombre.value = ""
            input_monto.value = ""
            page.update()
        except: pass

    def consultar_guru(e):
        if not input_chat.value.strip(): return
        prompt = f"Eres un coach financiero gracioso. Gastos actual: {datos_gastos}. Pregunta: {input_chat.value}"
        try:
            response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
            respuesta = response.text
        except Exception as ex:
            respuesta = f"Error: {ex}"
        chat_display.controls.append(ft.Text(f"🧙 Guru: {respuesta}", color="green", italic=True))
        input_chat.value = ""
        page.update()

    # Cargar la lista visual por primera vez
    actualizar_lista_visual()

    # --- CONTENEDORES DE VISTA ---
    container_gastos = ft.Column([
        ft.Text("Registro de Gastos", size=20, weight="bold"),
        input_nombre, input_monto, 
        ft.Button("Añadir Gasto", on_click=agregar_gasto, icon="add"),
        ft.Divider(),
        lista_visual
    ], visible=True, expand=True)

    container_ia = ft.Column([
        ft.Text("Money-Guru AI", size=20, weight="bold"),
        chat_display,
        ft.Row([input_chat, ft.IconButton("send", on_click=consultar_guru)])
    ], visible=False, expand=True)

    def cambiar_vista(e):
        idx = e.control.selected_index
        container_gastos.visible = (idx == 0)
        container_ia.visible = (idx == 1)
        page.update()

    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon="payments", label="Gastos"),
            ft.NavigationBarDestination(icon="psychology", label="IA Guru"),
        ],
        on_change=cambiar_vista
    )

    page.navigation_bar = nav_bar
    page.add(
        ft.Container(content=container_gastos, expand=True),
        ft.Container(content=container_ia, expand=True)
    )

if __name__ == "__main__":
    ft.run(main)