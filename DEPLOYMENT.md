# Guía de Despliegue - Finca API

## Configuración de Entornos

### Desarrollo Local

**Archivo de configuración:** `.env`
**Comando de ejecución:** `python run.py`
**Configuración:** DevelopmentConfig

```bash
# Ejecutar en desarrollo
python run.py
```

### Producción

**Archivo de configuración:** `.env.production`
**Comando de ejecución:** `gunicorn wsgi:app` o servidor web
**Configuración:** ProductionConfig
**Dominio:** `https://finca.isladigital.xyz`

```bash
# Configurar variable de entorno para producción
export FLASK_ENV=production

# Ejecutar con gunicorn
gunicorn --bind 0.0.0.0:8081 --workers 4 wsgi:app
```

## Configuraciones Principales

### Desarrollo (.env)
- **Dominio:** localhost
- **Puerto:** 8081
- **HTTPS:** Certificados locales
- **JWT_COOKIE_DOMAIN:** None
- **CORS:** Incluye localhost y 127.0.0.1

### Producción (.env.production)
- **Dominio:** finca.isladigital.xyz
- **Puerto:** 443 (HTTPS)
- **JWT_COOKIE_DOMAIN:** finca.isladigital.xyz
- **CORS:** Incluye dominios de producción

## Base de Datos

**Servidor:** isladigital.xyz:3311
**Base de datos:** finca
**Usuario:** fincau

## URLs de la API

### Desarrollo
- API Base: `https://localhost:8081/api/v1`
- Documentación: `https://localhost:8081/docs`
- Swagger JSON: `https://localhost:8081/swagger.json`

### Producción
- API Base: `https://finca.isladigital.xyz/api/v1`
- Documentación: `https://finca.isladigital.xyz/docs`
- Swagger JSON: `https://finca.isladigital.xyz/swagger.json`

## Despliegue con Docker

```bash
# Para desarrollo
docker-compose up

# Para producción, configurar FLASK_ENV=production en el entorno
export FLASK_ENV=production
docker-compose up
```

## Notas Importantes

1. **wsgi.py** detecta automáticamente el entorno basado en `FLASK_ENV`
2. **run.py** siempre usa configuración de desarrollo
3. Los certificados SSL están configurados para desarrollo local
4. En producción, el servidor web debe manejar HTTPS
5. Las cookies JWT están configuradas para cada dominio específico

## Troubleshooting

### Error de JWT Cookie Domain
- Verificar que `JWT_COOKIE_DOMAIN` coincida con el dominio actual
- En desarrollo debe ser `None`
- En producción debe ser `finca.isladigital.xyz`

### Error de CORS
- Verificar que el origen del frontend esté en `CORS_ORIGINS`
- Agregar nuevos dominios según sea necesario

### Error de Base de Datos
- Verificar conectividad a `isladigital.xyz:3311`
- Confirmar credenciales en el archivo .env correspondiente