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
    # Los envolvemos en un Container con color de fondo para distinguirlos
    container_gastos = ft.Column([
        ft.Text("Registro de Gastos", size=24, weight="bold", color="blue"),
        input_nombre, 
        input_monto, 
        ft.ElevatedButton("Añadir Gasto", on_click=agregar_gasto, icon="add", bgcolor="blue", color="white"),
        ft.Divider(),
        ft.Text("Historial:", size=16, weight="bold"),
        lista_visual
    ], visible=True, expand=True)

    container_ia = ft.Column([
        ft.Text("Money-Guru AI 🧙", size=24, weight="bold", color="green"),
        chat_display,
        ft.Row([
            input_chat, 
            ft.IconButton("send", on_click=consultar_guru, icon_color="green")
        ])
    ], visible=False, expand=True)

    # --- NAVEGACIÓN MANUAL (BOTONES SIMPLES) ---
    def mostrar_gastos(e):
        container_gastos.visible = True
        container_ia.visible = False
        btn_ir_gastos.bgcolor = "blue"
        btn_ir_ia.bgcolor = None
        page.update()

    def mostrar_ia(e):
        container_gastos.visible = False
        container_ia.visible = True
        btn_ir_gastos.bgcolor = None
        btn_ir_ia.bgcolor = "green"
        page.update()

    # Botones que actúan como pestañas
    btn_ir_gastos = ft.ElevatedButton("GASTOS", on_click=mostrar_gastos, bgcolor="blue", color="white")
    btn_ir_ia = ft.ElevatedButton("IA GURU", on_click=mostrar_ia, color="white")

    menu_superior = ft.Row([
        btn_ir_gastos,
        btn_ir_ia
    ], alignment=ft.MainAxisAlignment.CENTER)

    # Limpiamos y agregamos todo en orden
    page.clean()
    page.add(
        menu_superior,        # Los botones de navegación arriba
        ft.Divider(),         # Una línea separadora
        container_gastos,     # Contenido de gastos
        container_ia          # Contenido de IA (invisible al inicio)
    )

if __name__ == "__main__":
    ft.run(main)