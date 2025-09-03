#!/usr/bin/env python3
"""
Script para probar el rendimiento de los endpoints optimizados
Este archivo es un script de integración y se omite durante pytest.
"""

import pytest
pytest.skip("Integration performance script - skipped during pytest runs", allow_module_level=True)

import requests
import time
import json
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime

# Suprimir advertencias de SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_URL = "https://localhost:8081"
API_BASE = f"{BASE_URL}/api/v1"

def test_endpoint_performance(url, headers=None, iterations=3):
    """Probar el rendimiento de un endpoint múltiples veces"""
    if headers is None:
        headers = {"Content-Type": "application/json"}
    
    results = []
    etag = None
    
    print(f"\n🔍 Probando: {url}")
    print("=" * 60)
    
    for i in range(iterations):
        # Agregar ETag si está disponible de la iteración anterior
        test_headers = headers.copy()
        if etag and i > 0:
            test_headers['If-None-Match'] = etag
            print(f"  Iteración {i+1}: Enviando ETag {etag[:8]}...")
        else:
            print(f"  Iteración {i+1}: Sin ETag (primera consulta)")
        
        start_time = time.time()
        
        try:
            response = requests.get(url, headers=test_headers, verify=False, timeout=30)
            end_time = time.time()
            
            duration = (end_time - start_time) * 1000  # Convertir a ms
            
            # Obtener ETag de la respuesta
            if 'ETag' in response.headers:
                etag = response.headers['ETag']
            
            result = {
                'iteration': i + 1,
                'status_code': response.status_code,
                'duration_ms': round(duration, 2),
                'response_size': len(response.content),
                'etag': etag[:8] + '...' if etag else None,
                'cache_control': response.headers.get('Cache-Control'),
                'last_modified': response.headers.get('Last-Modified')
            }
            
            results.append(result)
            
            # Mostrar resultado
            if response.status_code == 304:
                print(f"    ✅ 304 Not Modified - {duration:.2f}ms (CACHE HIT)")
            elif response.status_code == 200:
                print(f"    📊 200 OK - {duration:.2f}ms - {len(response.content)} bytes")
            else:
                print(f"    ❌ {response.status_code} - {duration:.2f}ms")
            
            # Pausa entre iteraciones para simular uso real
            if i < iterations - 1:
                time.sleep(1)
                
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            results.append({
                'iteration': i + 1,
                'error': str(e),
                'duration_ms': None
            })
    
    return results

def analyze_results(results, endpoint_name):
    """Analizar los resultados de rendimiento"""
    print(f"\n📊 Análisis de {endpoint_name}:")
    print("-" * 40)
    
    successful_results = [r for r in results if 'duration_ms' in r and r['duration_ms'] is not None]
    
    if not successful_results:
        print("❌ No hay resultados exitosos para analizar")
        return
    
    durations = [r['duration_ms'] for r in successful_results]
    cache_hits = len([r for r in successful_results if r['status_code'] == 304])
    
    print(f"  • Total de consultas: {len(results)}")
    print(f"  • Consultas exitosas: {len(successful_results)}")
    print(f"  • Cache hits (304): {cache_hits}")
    print(f"  • Tiempo promedio: {sum(durations)/len(durations):.2f}ms")
    print(f"  • Tiempo mínimo: {min(durations):.2f}ms")
    print(f"  • Tiempo máximo: {max(durations):.2f}ms")
    
    if cache_hits > 0:
        cache_durations = [r['duration_ms'] for r in successful_results if r['status_code'] == 304]
        normal_durations = [r['duration_ms'] for r in successful_results if r['status_code'] == 200]
        
        if cache_durations and normal_durations:
            cache_avg = sum(cache_durations) / len(cache_durations)
            normal_avg = sum(normal_durations) / len(normal_durations)
            improvement = ((normal_avg - cache_avg) / normal_avg) * 100
            
            print(f"  • Tiempo promedio con caché: {cache_avg:.2f}ms")
            print(f"  • Tiempo promedio sin caché: {normal_avg:.2f}ms")
            print(f"  • 🚀 Mejora de rendimiento: {improvement:.1f}%")

def main():
    print("🚀 Prueba de Rendimiento - Sistema de Caché ETag")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Servidor: {API_BASE}")
    
    # Endpoints a probar
    endpoints = [
        {
            'name': 'Listar Animales',
            'url': f"{API_BASE}/animals/",
            'iterations': 4
        },
        {
            'name': 'Listar Especies',
            'url': f"{API_BASE}/breeds-species/species",
            'iterations': 4
        },
        {
            'name': 'Listar Razas',
            'url': f"{API_BASE}/breeds-species/breeds",
            'iterations': 4
        },
        {
            'name': 'Estadísticas de Animales',
            'url': f"{API_BASE}/animals/status",
            'iterations': 3
        }
    ]
    
    all_results = {}
    
    for endpoint in endpoints:
        results = test_endpoint_performance(
            endpoint['url'], 
            iterations=endpoint['iterations']
        )
        all_results[endpoint['name']] = results
        analyze_results(results, endpoint['name'])
    
    # Resumen general
    print("\n" + "=" * 60)
    print("📋 RESUMEN GENERAL")
    print("=" * 60)
    
    total_cache_hits = 0
    total_requests = 0
    
    for endpoint_name, results in all_results.items():
        successful = [r for r in results if 'duration_ms' in r and r['duration_ms'] is not None]
        cache_hits = len([r for r in successful if r['status_code'] == 304])
        
        total_cache_hits += cache_hits
        total_requests += len(successful)
        
        if successful:
            avg_time = sum(r['duration_ms'] for r in successful) / len(successful)
            print(f"  • {endpoint_name}: {avg_time:.2f}ms promedio, {cache_hits} cache hits")
    
    if total_requests > 0:
        cache_hit_rate = (total_cache_hits / total_requests) * 100
        print(f"\n🎯 Tasa de cache hits global: {cache_hit_rate:.1f}%")
        
        if cache_hit_rate > 50:
            print("✅ Excelente eficiencia de caché!")
        elif cache_hit_rate > 25:
            print("⚠️  Eficiencia de caché moderada")
        else:
            print("❌ Baja eficiencia de caché")
    
    # Guardar resultados detallados
    with open('performance_test_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'server': API_BASE,
            'results': all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Resultados detallados guardados en: performance_test_results.json")
    
    print("\n💡 Recomendaciones:")
    print("  • Los clientes deben enviar ETags en headers 'If-None-Match'")
    print("  • Implementar caché del lado del cliente para máxima eficiencia")
    print("  • Monitorear logs para verificar cache hits en producción")

if __name__ == "__main__":
    main()