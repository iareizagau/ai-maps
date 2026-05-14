import json
from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.gis.geos import LineString
from apps.adventure.models import TrailEdge

class Command(BaseCommand):
    help = 'Crea una red de senderos de prueba y ejecuta un cálculo de pgRouting'

    def handle(self, *args, **options):
        self.stdout.write("Limpiando datos antiguos...")
        TrailEdge.objects.all().delete()

        # Creamos una red simple: 3 puntos formando un triángulo
        # Punto 0: (0,0), Punto 1: (1,0), Punto 2: (0,1)
        
        self.stdout.write("Creando red de prueba (Triángulo)...")
        
        # Tramo A: Nodo 0 -> Nodo 1
        TrailEdge.objects.create(
            source=0, target=1, cost=10.0, reverse_cost=10.0,
            name="Senda Llana", highway="path", surface="dirt",
            geom=LineString((0,0), (1,0))
        )
        
        # Tramo B: Nodo 1 -> Nodo 2
        TrailEdge.objects.create(
            source=1, target=2, cost=15.0, reverse_cost=15.0,
            name="Subida Empinada", highway="track", surface="gravel",
            geom=LineString((1,0), (0,1))
        )
        
        # Tramo C: Nodo 0 -> Nodo 2 (Camino directo pero 'caro')
        TrailEdge.objects.create(
            source=0, target=2, cost=50.0, reverse_cost=50.0,
            name="Atajo por Pedrera", highway="path", surface="stone",
            geom=LineString((0,0), (0,1))
        )

        self.stdout.write("Ejecutando pgRouting (Dijkstra) de Nodo 0 a Nodo 2...")
        
        # Consulta SQL pura para pgRouting
        query = """
            SELECT * FROM pgr_dijkstra(
                'SELECT id, source, target, cost FROM adventure_trails',
                0, -- Inicio
                2, -- Fin
                directed := false
            );
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            
            self.stdout.write(self.style.SUCCESS("\n¡Ruta encontrada!"))
            self.stdout.write("Paso | Nodo | Arista (ID) | Coste Acumulado")
            self.stdout.write("-" * 45)
            
            for row in rows:
                # pgr_dijkstra v3.0+ devuelve: seq, path_seq, start_vid, end_vid, node, edge, cost, agg_cost
                seq, path_seq, start_vid, end_vid, node, edge, cost, agg_cost = row
                self.stdout.write(f" {seq}   |  {node}   |      {edge if edge != -1 else 'FIN'}      | {agg_cost}")

        self.stdout.write("\nNota: Fíjate que ha preferido ir de 0->1 y luego 1->2 (coste 25) ")
        self.stdout.write("en lugar de ir directo 0->2 (coste 50). ¡Esa es la magia!")
