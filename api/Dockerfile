# autoformularz API. Official base images, pinned versions, non-root user, secrets only at runtime.
# Debian slim (not Alpine): LibreOffice and the PDF/imaging wheels are built for glibc.

FROM python:3.14.10-slim-trixie AS build
RUN pip install --no-cache-dir uv==0.13.0
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PYTHON=python3.14
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.14.10-slim-trixie
# LibreOffice reads legacy .doc and .ods. Build with --build-arg WITH_LIBREOFFICE=0 for a smaller image.
ARG WITH_LIBREOFFICE=1
RUN if [ "$WITH_LIBREOFFICE" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends libreoffice-writer-nogui libreoffice-calc-nogui \
      && rm -rf /var/lib/apt/lists/*; \
    fi \
    && groupadd --system app && useradd --system --gid app --no-create-home --home-dir /tmp app
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HOME=/tmp
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
CMD ["uvicorn", "autoformularz.main:app", "--host", "0.0.0.0", "--port", "8000"]
