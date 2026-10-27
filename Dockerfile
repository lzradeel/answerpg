FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MODEL_DIR=/models

WORKDIR /srv/answerpg

COPY pyproject.toml README.md ./
COPY answerpg ./answerpg
RUN pip install . && python -m answerpg.encoders

# Both encoders ship inside the image, so the container never has to reach the Hugging Face Hub.
ENV HF_HUB_OFFLINE=1

COPY scripts ./scripts
COPY data ./data

RUN useradd --create-home --uid 1000 answerpg && chown -R answerpg:answerpg /models
USER answerpg

EXPOSE 8000
CMD ["uvicorn", "answerpg.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
