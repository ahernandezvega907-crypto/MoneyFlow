import flet as ft

def main(page: ft.Page):
    page.title = "Debug MoneyFlow"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0A0A0A"
    page.padding = 20

    # Variables simuladas
    user_email = "test@test.com"
    colors = {
        "primary": "#00BFA6",
        "text": "#FFFFFF",
        "text_secondary": "#B0B0B0",
        "surface": "#1E1E1E",
        "bg": "#0A0A0A",
    }

    # Pestañas de ejemplo
    vista1 = ft.Column([ft.Text("Gastos", color=colors["text"])])
    vista2 = ft.Column([ft.Text("Presupuestos", color=colors["text"])])
    vista3 = ft.Column([ft.Text("Dashboard", color=colors["text"])])
    vista4 = ft.Column([ft.Text("IA", color=colors["text"])])
    vista5 = ft.Column([ft.Text("Estadísticas", color=colors["text"])])
    vista6 = ft.Column([ft.Text("Perfil", color=colors["text"])])

    vistas = [vista1, vista2, vista3, vista4, vista5, vista6]
    for v in vistas[1:]:
        v.visible = False

    def cambiar(e):
        for i, v in enumerate(vistas):
            v.visible = (i == e.control.selected_index)
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=cambiar,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ATTACH_MONEY, label="GASTOS"),
            ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART, label="PRESUP."),
            ft.NavigationBarDestination(icon=ft.Icons.DASHBOARD, label="DASHBOARD"),
            ft.NavigationBarDestination(icon=ft.Icons.PSYCHOLOGY, label="IA"),
            ft.NavigationBarDestination(icon=ft.Icons.SHOW_CHART, label="STATS"),
            ft.NavigationBarDestination(icon=ft.Icons.PERSON, label="PERFIL"),
        ],
        bgcolor=colors["surface"],
    )

    page.add(*vistas)
    page.update()

ft.app(target=main)