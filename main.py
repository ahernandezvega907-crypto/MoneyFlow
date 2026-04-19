import flet as ft
import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def main(page: ft.Page):
    page.title = "MoneyFlow AI"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10

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

    datos_gastos = cargar_datos()

    # --- ELEMENTOS DE INTERFAZ ---
    input_nombre = ft.TextField(label="Gasto", expand=True)
    input_monto = ft.TextField(label="Monto $", width=90, keyboard_type=ft.KeyboardType.NUMBER)
    lista_visual = ft.ListView(expand=True, spacing=5)
    chat_display = ft.Column(scroll=ft.ScrollMode.ALWAYS, height=300, expand=True)
    input_chat = ft.TextField(hint_text="Pregunta al Guru...", expand=True)

    def actualizar_lista_visual():
        lista_visual.controls.clear()
        for gasto in reversed(datos_gastos):
            lista_visual.controls.append(
                ft.Container(
                    bgcolor="surface", 
                    border_radius=8,
                    padding=10,
                    content=ft.Row([
                        ft.Icon("payments", color="blue"),
                        # 'expand=True' obliga al nombre a usar todo el espacio y empuja el monto a la derecha
                        ft.Text(gasto["nombre"], size=16, weight="bold", expand=True),
                        ft.Text(f"${gasto['monto']:.2f}", size=16, weight="bold", color="green"),
                    ])
                )
            )
        page.update()

    def agregar_gasto(e):
        try:
            if input_nombre.value and input_monto.value:
                monto = float(input_monto.value)
                datos_gastos.append({"nombre": input_nombre.value, "monto": monto})
                guardar_datos()
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
        
        chat_display.controls.append(
            ft.Container(
                content=ft.Text(f"🧙 Guru: {respuesta}", color="green", italic=True),
                padding=10,
                bgcolor="black",
                border_radius=10
            )
        )
        input_chat.value = ""
        page.update()

    actualizar_lista_visual()

    # --- CONTENEDORES DE VISTA ---
    container_gastos = ft.Column([
        ft.Text("Registro de Gastos", size=22, weight="bold", color="blue"),
        ft.Row([input_nombre, input_monto]),
        ft.FilledButton("Añadir Gasto", on_click=agregar_gasto, icon="add", width=400),
        ft.Divider(),
        ft.Text("Historial:", size=16, weight="bold"),
        lista_visual
    ], visible=True, expand=True)

    container_ia = ft.Column([
        ft.Text("Money-Guru AI 🧙", size=22, weight="bold", color="green"),
        chat_display,
        ft.Row([
            input_chat, 
            # Cambiado a FilledButton para evitar errores de IconButton
            ft.FilledButton("Enviar", on_click=consultar_guru, icon="send", bgcolor="green")
        ])
    ], visible=False, expand=True)

    # --- NAVEGACIÓN ---
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

    btn_ir_gastos = ft.FilledButton("GASTOS", on_click=mostrar_gastos, bgcolor="blue")
    btn_ir_ia = ft.FilledButton("IA GURU", on_click=mostrar_ia)

    menu_superior = ft.Row([btn_ir_gastos, btn_ir_ia], alignment=ft.MainAxisAlignment.CENTER)

    page.add(
        menu_superior,
        ft.Divider(),
        container_gastos,
        container_ia
    )

if __name__ == "__main__":
    ft.run(main)