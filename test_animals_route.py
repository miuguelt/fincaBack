#!/usr/bin/env python3
"""
Script para probar directamente la ruta de animales
y diagnosticar problemas de funcionamiento.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.animals import Animals
from flask import Flask
import json

def test_animals_route():
    """Probar la ruta de animales directamente"""
    print("🔍 Probando la ruta de listar animales...")
    print("=" * 50)
    
    try:
        # Crear la aplicación Flask
        app = create_app('development')
        
        with app.app_context():
            # Verificar conexión a la base de datos
            try:
                total_animals = Animals.query.count()
                print(f"✅ Conexión a BD exitosa: {total_animals} animales en total")
            except Exception as e:
                print(f"❌ Error de conexión a BD: {e}")
                return False
            
            # Probar la consulta optimizada
            try:
                from sqlalchemy.orm import joinedload
                from app.models.breeds import Breeds
                
                # Consulta optimizada con eager loading
                query = Animals.query.options(
                    joinedload(Animals.breed).joinedload(Breeds.species)
                )
                
                # Obtener algunos animales para probar
                animals = query.limit(5).all()
                print(f"✅ Consulta optimizada exitosa: {len(animals)} animales obtenidos")
                
                # Probar serialización
                animals_json = []
                for animal in animals:
                    try:
                        animal_data = animal.to_json()
                        animals_json.append(animal_data)
                        print(f"  • Animal {animal.id}: {animal.record} - {animal.sex} - {animal.status}")
                    except Exception as e:
                        print(f"  ❌ Error serializando animal {animal.id}: {e}")
                
                print(f"✅ Serialización exitosa: {len(animals_json)} animales serializados")
                
            except Exception as e:
                print(f"❌ Error en consulta optimizada: {e}")
                return False
            
            # Probar paginación
            try:
                page = 1
                per_page = 10
                
                pagination = Animals.query.paginate(
                    page=page,
                    per_page=per_page,
                    error_out=False
                )
                
                result = {
                    'animals': [animal.to_json() for animal in pagination.items],
                    'total': pagination.total,
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
                
                print(f"✅ Paginación exitosa:")
                print(f"  • Total: {result['total']}")
                print(f"  • Página: {result['page']}/{result['pages']}")
                print(f"  • Por página: {result['per_page']}")
                print(f"  • Tiene siguiente: {result['has_next']}")
                print(f"  • Tiene anterior: {result['has_prev']}")
                print(f"  • Animales en esta página: {len(result['animals'])}")
                
                # Verificar que no hay campos null
                null_fields = []
                for field, value in result.items():
                    if value is None:
                        null_fields.append(field)
                
                if null_fields:
                    print(f"⚠️  Campos null encontrados: {null_fields}")
                else:
                    print("✅ No hay campos null en la respuesta")
                
                return True
                
            except Exception as e:
                print(f"❌ Error en paginación: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_endpoint_simulation():
    """Simular el endpoint completo"""
    print("\n🧪 Simulando endpoint completo...")
    print("=" * 50)
    
    try:
        app = create_app('development')
        
        with app.test_client() as client:
            # Simular request sin autenticación
            response = client.get('/api/v1/animals/')
            print(f"Status sin auth: {response.status_code}")
            
            if response.status_code == 401:
                print("✅ Autenticación requerida (esperado)")
            else:
                print(f"⚠️  Status inesperado: {response.status_code}")
                print(f"Respuesta: {response.get_data(as_text=True)[:200]}...")
            
            return True
            
    except Exception as e:
        print(f"❌ Error simulando endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 Diagnóstico de la Ruta de Animales")
    print("=" * 50)
    
    # Test 1: Funcionalidad básica
    success1 = test_animals_route()
    
    # Test 2: Simulación de endpoint
    success2 = test_endpoint_simulation()
    
    print("\n" + "=" * 50)
    print("📊 RESUMEN")
    print("=" * 50)
    
    if success1:
        print("✅ Consulta y serialización: FUNCIONANDO")
    else:
        print("❌ Consulta y serialización: CON PROBLEMAS")
    
    if success2:
        print("✅ Endpoint simulation: FUNCIONANDO")
    else:
        print("❌ Endpoint simulation: CON PROBLEMAS")
    
    if success1 and success2:
        print("\n🎉 La ruta de animales debería funcionar correctamente")
        print("💡 Si hay problemas, verificar:")
        print("   • Servidor Flask ejecutándose")
        print("   • Autenticación JWT")
        print("   • Configuración de CORS")
    else:
        print("\n⚠️  Hay problemas que necesitan corrección")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)