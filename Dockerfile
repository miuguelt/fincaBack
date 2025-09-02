FROM python:3.12-alpine AS backend

# Establecer el directorio de trabajo
WORKDIR /app

RUN apk add --no-cache build-base libpq-dev
# Copiar requirements.txt e instalar dependencias
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

EXPOSE 8081
#CMD ["python", "run.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:8081", "--workers", "4", "--forwarded-allow-ips=*", "wsgi:app"]
