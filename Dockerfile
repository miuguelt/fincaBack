###############
# Dockerfile optimizado para Flask + Gunicorn
# - Elimina CMD duplicado
# - Instala solo dependencias necesarias en Alpine
# - Usa build deps temporales para compilar cryptography/psutil y luego las elimina
# - Usa usuario no root
# - Añade healthcheck básico
###############

FROM python:3.12-alpine AS app

# Variables de entorno Python
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	PORT=8081

WORKDIR /app

# Dependencias de runtime (openssl, libffi). PyMySQL es puro Python, pero cryptography necesita libs
RUN apk add --no-cache libffi openssl

# Dependencias de build temporales para compilar cryptography / psutil
RUN apk add --no-cache --virtual .build-deps \
		build-base \
		linux-headers \
		musl-dev \
		python3-dev \
		libffi-dev \
		openssl-dev \
		cargo

# Copiar solo requirements primero para aprovechar la cache
COPY requirements.txt ./

RUN pip install --upgrade pip && \
	pip install -r requirements.txt && \
	apk del .build-deps

# Copiar el resto del código
COPY . .

# Crear usuario no root
RUN addgroup -S app && adduser -S app -G app && \
	chown -R app:app /app
USER app

EXPOSE 8081

# Healthcheck (el endpoint /health ya existe en la app)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:${PORT}/health || exit 1

# Ejecutar con Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8081", "--workers", "4", "--forwarded-allow-ips=*", "wsgi:app"]
