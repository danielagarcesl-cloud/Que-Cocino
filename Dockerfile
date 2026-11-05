# ---------- etapa 1: instalar dependencias ----------
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- etapa 2: imagen final, liviana y sin privilegios ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /srv
COPY --from=builder /install /usr/local
COPY app/ app/
COPY data/ data/
COPY config/ config/
COPY prompts/ prompts/
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin quecocino
USER 10001
EXPOSE 8080
# forma shell: Heroku y Cloud Run inyectan la variable PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
