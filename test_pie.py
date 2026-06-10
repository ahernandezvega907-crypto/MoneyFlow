import flet as ft
from flet.charts import PieChart, PieChartSection

def main(page: ft.Page):
    page.add(ft.Text("Probando PieChart"))
    chart = PieChart(
        sections=[
            PieChartSection(50, title="A", color=ft.Colors.BLUE),
            PieChartSection(30, title="B", color=ft.Colors.RED),
        ]
    )
    page.add(chart)

ft.app(target=main)
