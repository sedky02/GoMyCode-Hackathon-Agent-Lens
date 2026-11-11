FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agentlens/ agentlens/
COPY scripts/ scripts/
COPY data/ data/
COPY evaluate.py generate_dataset.py supplyzpro_agent_logs.db ./

RUN useradd --create-home app && mkdir /data && chown -R app:app /app /data
USER app

ENV AGENTLENS_DB=/data/agentlens.db \
    HF_HOME=/data/huggingface \
    PYTHONUNBUFFERED=1

# The dashboard's Evaluation panel reads this report; it is computed from the code in this image.
RUN python evaluate.py --mode rules

EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/healthz', timeout=2)"
CMD ["uvicorn", "agentlens.api:app", "--host", "0.0.0.0", "--port", "8100"]
