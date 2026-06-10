import flet as ft

def main(page: ft.Page):
    page.title = "Prueba navegación"
    page.bgcolor = "#0A0A0A"
    
    # Simular pantallas
    vista1 = ft.Column([ft.Text("Gastos", color="white")], visible=True)
    vista2 = ft.Column([ft.Text("Perfil", color="white")], visible=False)
    
    def cambiar(e):
        vista1.visible = e.control.selected_index == 0
        vista2.visible = e.control.selected_index == 1
        page.update()
    
    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=cambiar,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ATTACH_MONEY, label="GASTOS"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON, label="PERFIL"),
        ],
        bgcolor="#1E1E1E",
    )
    
    page.add(vista1, vista2)
    page.update()

ft.app(target=main)