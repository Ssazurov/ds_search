FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium && chmod -R a+rX /ms-playwright

# Публикация внешнего сайта из админки (ADR-0019): ds_site монтируется томом, тут — git, gh, node.
ARG NODE_VERSION=22.23.1
RUN apt-get update && apt-get install -y --no-install-recommends git gh xz-utils \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
       | tar -xJ -C /usr/local --strip-components=1 --exclude='*.md' --exclude=LICENSE \
    && node --version && git --version && gh --version | head -1

# Новые Python-зависимости добавлять СЮДА (requirements-extra.txt), а не в requirements.txt:
# слой стоит после chromium/node, поэтому его изменение не перекачивает тяжёлые слои.
COPY requirements-extra.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-extra.txt

COPY . .

# issue #325: MD/JSON-ссылки на вкладке Документы отдаются через встроенную
# статику Streamlit (enableStaticServing, .streamlit/config.toml), т.к.
# file:// не открывается браузером с http-страницы. data — volume-mount;
# смонтирован ДВАЖДЫ (docker-compose.yml: /app/data и /app/ui/static/data),
# а не через symlink — Streamlit's build_safe_abspath() резолвит realpath и
# отклоняет (400) любой путь, уходящий symlink'ом за пределы app_static_root.
RUN mkdir -p /app/ui/static/data

EXPOSE 8501
CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
