#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico Completo de Token JWT - Análisis Exhaustivo
Finca Villa Luz API - Diagnóstico de Autenticación

Este script analiza todas las posibles causas de por qué un token JWT
válido es rechazado por el servidor.
"""

import requests
import json
import time
from datetime import datetime, timezone
import urllib3
import jwt
import base64
from typing import Dict, Any
import os

# Deshabilitar warnings SSL para desarrollo
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TokenDiagnostic:
    def __init__(self, base_url: str = 'https://127.0.0.1:8081/api/v1'):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.verify = False
        
        # Headers por defecto
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'TokenDiagnostic/1.0'
        })
        
        # Credenciales de prueba
        self.test_credentials = {
            "identification": 1098,
            "password": "admin123"
        }
        
        # Variables para almacenar tokens
        self.access_token = None
        self.refresh_token = None
        self.login_response = None
        
        print("🔍 DIAGNÓSTICO COMPLETO DE TOKEN JWT")
        print(f"Base URL: {self.base_url}")
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

    def print_step(self, step_number: int, description: str):
        """Imprime el paso actual del diagnóstico"""
        print(f"\n{step_number}️⃣ {description}")
        print("-" * 50)

    def print_result(self, success: bool, message: str, details: str = None):
        """Imprime el resultado de una operación"""
        icon = "✅" if success else "❌"
        print(f"{icon} {message}")
        if details:
            print(f"   {details}")

    def decode_jwt_token(self, token: str) -> Dict[str, Any]:
        """Decodifica un token JWT sin verificar la firma"""
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            return decoded
        except Exception as e:
            print(f"   ❌ Error decodificando token: {str(e)}")
            return {}

    def step1_login_and_extract_tokens(self):
        """Paso 1: Login y extracción de tokens"""
        self.print_step(1, "Login y extracción de tokens")
        
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json=self.test_credentials,
                timeout=10
            )
            
            if response.status_code == 200:
                self.login_response = response.json()
                
                # Extraer tokens de cookies
                cookies = self.session.cookies
                if 'access_token_cookie' in cookies:
                    self.access_token = cookies['access_token_cookie']
                    self.print_result(True, "Token de acceso extraído de cookies")
                else:
                    self.print_result(False, "Token de acceso NO encontrado en cookies")
                    return False
                
                if 'refresh_token_cookie' in cookies:
                    self.refresh_token = cookies['refresh_token_cookie']
                    self.print_result(True, "Token de refresh extraído de cookies")
                else:
                    self.print_result(False, "Token de refresh NO encontrado en cookies")
                
                return True
            else:
                self.print_result(False, f"Login falló con status {response.status_code}")
                return False
                
        except Exception as e:
            self.print_result(False, f"Error en login: {str(e)}")
            return False

    def step2_analyze_token_structure(self):
        """Paso 2: Analizar estructura del token"""
        self.print_step(2, "Análisis de estructura del token")
        
        if not self.access_token:
            self.print_result(False, "No hay token para analizar")
            return False
        
        # Verificar estructura JWT (header.payload.signature)
        parts = self.access_token.split('.')
        if len(parts) != 3:
            self.print_result(False, f"Token malformado - tiene {len(parts)} partes en lugar de 3")
            return False
        
        self.print_result(True, "Token tiene estructura JWT válida (3 partes)")
        
        # Decodificar header
        try:
            header_decoded = base64.urlsafe_b64decode(parts[0] + '==').decode('utf-8')
            header = json.loads(header_decoded)
            print(f"   Header: {json.dumps(header, indent=2)}")
            
            if header.get('alg') != 'HS256':
                self.print_result(False, f"Algoritmo inesperado: {header.get('alg')}")
            else:
                self.print_result(True, "Algoritmo correcto: HS256")
                
        except Exception as e:
            self.print_result(False, f"Error decodificando header: {str(e)}")
            return False
        
        # Decodificar payload
        try:
            payload_decoded = base64.urlsafe_b64decode(parts[1] + '==').decode('utf-8')
            payload = json.loads(payload_decoded)
            print(f"   Payload: {json.dumps(payload, indent=2)[:500]}...")
            self.print_result(True, "Payload decodificado correctamente")
            
        except Exception as e:
            self.print_result(False, f"Error decodificando payload: {str(e)}")
            return False
        
        return True

    def step3_test_token_validation(self):
        """Paso 3: Probar validación del token en diferentes formas"""
        self.print_step(3, "Pruebas de validación del token")
        
        if not self.access_token:
            self.print_result(False, "No hay token para validar")
            return False
        
        # Prueba 1: Enviar token en cookie (automático)
        print("\n🔸 Prueba 1: Token en cookie (automático)")
        try:
            response = self.session.get(f"{self.base_url}/auth/test", timeout=10)
            if response.status_code == 200:
                self.print_result(True, "Token válido vía cookie")
            else:
                self.print_result(False, f"Token rechazado vía cookie (Status: {response.status_code})")
                if response.content:
                    try:
                        error_data = response.json()
                        print(f"   Error: {error_data.get('message', 'Sin mensaje')}")
                    except:
                        print(f"   Respuesta: {response.text[:200]}")
        except Exception as e:
            self.print_result(False, f"Error probando token vía cookie: {str(e)}")
        
        # Prueba 2: Enviar token en header Authorization
        print("\n🔸 Prueba 2: Token en header Authorization")
        try:
            headers = {'Authorization': f'Bearer {self.access_token}'}
            response = requests.get(
                f"{self.base_url}/auth/test",
                headers=headers,
                verify=False,
                timeout=10
            )
            if response.status_code == 200:
                self.print_result(True, "Token válido vía header Authorization")
            else:
                self.print_result(False, f"Token rechazado vía header (Status: {response.status_code})")
                if response.content:
                    try:
                        error_data = response.json()
                        print(f"   Error: {error_data.get('message', 'Sin mensaje')}")
                    except:
                        print(f"   Respuesta: {response.text[:200]}")
        except Exception as e:
            self.print_result(False, f"Error probando token vía header: {str(e)}")
        
        # Prueba 3: Enviar token manualmente en cookie
        print("\n🔸 Prueba 3: Token manual en cookie")
        try:
            cookies = {'access_token_cookie': self.access_token}
            response = requests.get(
                f"{self.base_url}/auth/test",
                cookies=cookies,
                verify=False,
                timeout=10
            )
            if response.status_code == 200:
                self.print_result(True, "Token válido vía cookie manual")
            else:
                self.print_result(False, f"Token rechazado vía cookie manual (Status: {response.status_code})")
        except Exception as e:
            self.print_result(False, f"Error probando token vía cookie manual: {str(e)}")
        
        return True

    def step4_analyze_server_logs(self):
        """Paso 4: Analizar qué está recibiendo el servidor"""
        self.print_step(4, "Análisis de lo que recibe el servidor")
        
        # Hacer una petición con máximo detalle
        print("\n🔸 Petición detallada al servidor")
        try:
            # Preparar headers completos
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'TokenDiagnostic/1.0',
                'Authorization': f'Bearer {self.access_token}',
                'X-Debug': 'true'
            }
            
            # Preparar cookies
            cookies = {
                'access_token_cookie': self.access_token,
                'refresh_token_cookie': self.refresh_token
            }
            
            print(f"   Enviando headers: {list(headers.keys())}")
            print(f"   Enviando cookies: {list(cookies.keys())}")
            print(f"   Token length: {len(self.access_token)} caracteres")
            
            response = requests.get(
                f"{self.base_url}/auth/test",
                headers=headers,
                cookies=cookies,
                verify=False,
                timeout=10
            )
            
            print(f"   Status recibido: {response.status_code}")
            print(f"   Headers de respuesta: {dict(response.headers)}")
            
            if response.content:
                try:
                    response_data = response.json()
                    print(f"   Respuesta JSON: {json.dumps(response_data, indent=2)}")
                except:
                    print(f"   Respuesta texto: {response.text}")
            
        except Exception as e:
            self.print_result(False, f"Error en petición detallada: {str(e)}")
        
        return True

    def step5_test_jwt_secret(self):
        """Paso 5: Probar validación con diferentes secretos JWT"""
        self.print_step(5, "Prueba de secretos JWT")
        
        if not self.access_token:
            self.print_result(False, "No hay token para validar")
            return False
        
        # Lista de posibles secretos
        possible_secrets = [
            'your-secret-key',
            'dev-secret-key',
            'development-secret',
            'flask-jwt-secret',
            'secret-key',
            os.getenv('JWT_SECRET_KEY', 'default-secret')
        ]
        
        print(f"\n🔸 Probando {len(possible_secrets)} posibles secretos")
        
        for i, secret in enumerate(possible_secrets, 1):
            try:
                decoded = jwt.decode(self.access_token, secret, algorithms=['HS256'])
                self.print_result(True, f"Token válido con secreto #{i}: '{secret[:10]}...'")
                print(f"   Usuario: {decoded.get('sub', {}).get('fullname', 'N/A')}")
                return True
            except jwt.ExpiredSignatureError:
                self.print_result(False, f"Secreto #{i} correcto pero token expirado")
            except jwt.InvalidSignatureError:
                self.print_result(False, f"Secreto #{i} incorrecto: '{secret[:10]}...'")
            except Exception as e:
                self.print_result(False, f"Secreto #{i} error: {str(e)}")
        
        self.print_result(False, "Ningún secreto probado funcionó")
        return False

    def step6_test_cookie_configuration(self):
        """Paso 6: Probar configuración de cookies"""
        self.print_step(6, "Análisis de configuración de cookies")
        
        # Analizar cookies establecidas
        print("\n🔸 Análisis de cookies del navegador")
        cookies = self.session.cookies
        
        for cookie in cookies:
            print(f"   Cookie: {cookie.name}")
            print(f"     Valor: {cookie.value[:50]}...")
            print(f"     Dominio: {cookie.domain}")
            print(f"     Path: {cookie.path}")
            print(f"     Secure: {cookie.secure}")
            print(f"     HttpOnly: {cookie.has_nonstandard_attr('HttpOnly')}")
            print(f"     SameSite: {cookie.get_nonstandard_attr('SameSite', 'None')}")
            print(f"     Expires: {cookie.expires}")
            print()
        
        # Probar diferentes configuraciones de dominio
        print("\n🔸 Probando diferentes dominios")
        test_domains = ['127.0.0.1', 'localhost', None]
        
        for domain in test_domains:
            try:
                session_test = requests.Session()
                session_test.verify = False
                
                # Establecer cookie manualmente
                session_test.cookies.set(
                    'access_token_cookie',
                    self.access_token,
                    domain=domain,
                    path='/'
                )
                
                response = session_test.get(f"{self.base_url}/auth/test", timeout=10)
                
                if response.status_code == 200:
                    self.print_result(True, f"Cookie funciona con dominio: {domain}")
                else:
                    self.print_result(False, f"Cookie falla con dominio: {domain} (Status: {response.status_code})")
                    
            except Exception as e:
                self.print_result(False, f"Error probando dominio {domain}: {str(e)}")
        
        return True

    def step7_test_cors_configuration(self):
        """Paso 7: Probar configuración CORS"""
        self.print_step(7, "Análisis de configuración CORS")
        
        # Probar diferentes orígenes
        test_origins = [
            'https://localhost:5175',
            'https://127.0.0.1:5175',
            'http://localhost:5175',
            'http://127.0.0.1:5175'
        ]
        
        for origin in test_origins:
            try:
                headers = {
                    'Origin': origin,
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.access_token}'
                }
                
                cookies = {'access_token_cookie': self.access_token}
                
                response = requests.get(
                    f"{self.base_url}/auth/test",
                    headers=headers,
                    cookies=cookies,
                    verify=False,
                    timeout=10
                )
                
                cors_headers = {
                    'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                    'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials'),
                    'Vary': response.headers.get('Vary')
                }
                
                if response.status_code == 200:
                    self.print_result(True, f"CORS OK con origen: {origin}")
                else:
                    self.print_result(False, f"CORS falla con origen: {origin} (Status: {response.status_code})")
                
                print(f"   CORS headers: {cors_headers}")
                
            except Exception as e:
                self.print_result(False, f"Error probando CORS con {origin}: {str(e)}")
        
        return True

    def step8_test_server_configuration(self):
        """Paso 8: Probar configuración del servidor"""
        self.print_step(8, "Análisis de configuración del servidor")
        
        # Probar endpoint de configuración si existe
        try:
            response = requests.get(f"{self.base_url.replace('/api/v1', '')}/health", verify=False, timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(f"   Estado del servidor: {health_data.get('status')}")
                print(f"   Timestamp servidor: {health_data.get('timestamp')}")
                
                # Comparar tiempo
                if 'timestamp' in health_data:
                    server_time = datetime.fromisoformat(health_data['timestamp'].replace('Z', '+00:00'))
                    current_time = datetime.now(timezone.utc)
                    time_diff = (current_time - server_time).total_seconds()
                    
                    if abs(time_diff) > 300:  # 5 minutos
                        self.print_result(False, f"Diferencia de tiempo significativa: {time_diff:.0f} segundos")
                    else:
                        self.print_result(True, f"Sincronización de tiempo OK: {time_diff:.0f} segundos")
                        
        except Exception as e:
            self.print_result(False, f"Error verificando configuración del servidor: {str(e)}")
        
        # Probar diferentes endpoints para ver patrones
        test_endpoints = ['/auth/test', '/auth/me', '/users/']
        
        print("\n🔸 Probando diferentes endpoints")
        for endpoint in test_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}", timeout=10)
                
                if response.status_code == 200:
                    self.print_result(True, f"Endpoint {endpoint} funciona")
                elif response.status_code == 401:
                    self.print_result(False, f"Endpoint {endpoint} rechaza token (401)")
                elif response.status_code == 404:
                    self.print_result(False, f"Endpoint {endpoint} no encontrado (404)")
                else:
                    self.print_result(False, f"Endpoint {endpoint} error {response.status_code}")
                    
            except Exception as e:
                self.print_result(False, f"Error probando {endpoint}: {str(e)}")
        
        return True

    def run_complete_diagnostic(self):
        """Ejecuta el diagnóstico completo"""
        start_time = time.time()
        results = []
        
        # Ejecutar todos los pasos
        diagnostic_steps = [
            ("Login y extracción de tokens", self.step1_login_and_extract_tokens),
            ("Análisis de estructura del token", self.step2_analyze_token_structure),
            ("Pruebas de validación del token", self.step3_test_token_validation),
            ("Análisis de lo que recibe el servidor", self.step4_analyze_server_logs),
            ("Prueba de secretos JWT", self.step5_test_jwt_secret),
            ("Análisis de configuración de cookies", self.step6_test_cookie_configuration),
            ("Análisis de configuración CORS", self.step7_test_cors_configuration),
            ("Análisis de configuración del servidor", self.step8_test_server_configuration)
        ]
        
        for step_name, step_function in diagnostic_steps:
            try:
                success = step_function()
                results.append((step_name, success))
                
                # Pausa entre pasos
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error en {step_name}: {str(e)}")
                results.append((step_name, False))
        
        # Generar reporte final
        self.generate_diagnostic_report(results, time.time() - start_time)

    def generate_diagnostic_report(self, results: list, execution_time: float):
        """Genera el reporte final del diagnóstico"""
        print("\n" + "=" * 70)
        print("📊 REPORTE FINAL DE DIAGNÓSTICO DE TOKEN")
        print("=" * 70)
        
        total_steps = len(results)
        successful_steps = len([r for r in results if r[1]])
        failed_steps = total_steps - successful_steps
        
        print(f"\n📋 RESUMEN:")
        print(f"   • Total de pasos: {total_steps}")
        print(f"   • Exitosos: {successful_steps} ✅")
        print(f"   • Fallidos: {failed_steps} ❌")
        print(f"   • Tiempo de ejecución: {execution_time:.2f} segundos")
        
        print(f"\n📝 DETALLE DE RESULTADOS:")
        for step_name, success in results:
            icon = "✅" if success else "❌"
            print(f"   {icon} {step_name}")
        
        # Análisis de posibles causas
        print(f"\n🔍 POSIBLES CAUSAS DEL PROBLEMA:")
        
        if not results[0][1]:  # Login falló
            print(f"   🔸 Problema de autenticación básica")
        elif not results[1][1]:  # Estructura del token
            print(f"   🔸 Token malformado o corrupto")
        elif not results[4][1]:  # Secreto JWT
            print(f"   🔸 Secreto JWT incorrecto en el servidor")
        elif not results[5][1]:  # Configuración de cookies
            print(f"   🔸 Problema de configuración de cookies (dominio, path, etc.)")
        elif not results[6][1]:  # CORS
            print(f"   🔸 Problema de configuración CORS")
        else:
            print(f"   🔸 Problema de configuración del servidor Flask-JWT")
            print(f"   🔸 Middleware de autenticación no configurado correctamente")
            print(f"   🔸 Problema de sincronización de tiempo")
        
        print(f"\n💡 RECOMENDACIONES:")
        print(f"   1. Verificar configuración JWT_SECRET_KEY en el servidor")
        print(f"   2. Verificar configuración de cookies (dominio, secure, samesite)")
        print(f"   3. Verificar configuración CORS para el origen correcto")
        print(f"   4. Verificar que Flask-JWT esté configurado correctamente")
        print(f"   5. Verificar logs del servidor Flask para más detalles")
        
        print(f"\n🕒 Diagnóstico completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

def main():
    """Función principal"""
    diagnostic = TokenDiagnostic()
    diagnostic.run_complete_diagnostic()

if __name__ == "__main__":
    main()