# CYCLO-NEXUS inference service — CPU-only image (master plan v4 Task 6.2 / v3 Micro-Task 5.2)
#
# Build from the REPOSITORY ROOT (the service imports forecaster/ and loads vision/ weights):
#   docker build -f inference/Dockerfile -t cyclonexus-inference .
# Run:
#   docker run -p 7860:7860 -e INFERENCE_API_KEY=<secret> cyclonexus-inference
# Hugging Face Spaces (Docker SDK) expects port 7860.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Runtime libraries needed by OpenCV (pulled in by ultralytics)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU wheels only — avoids the multi-GB CUDA runtime
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
COPY inference/requirements.txt inference/requirements.txt
RUN pip install -r inference/requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install opencv-python-headless

COPY inference/ inference/
COPY forecaster/ forecaster/
COPY vision/weights/ vision/weights/

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 7860
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/health').status == 200 else 1)"
CMD ["uvicorn", "inference.serve:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
