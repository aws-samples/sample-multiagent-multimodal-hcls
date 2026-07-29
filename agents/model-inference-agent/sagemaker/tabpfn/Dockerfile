FROM public.ecr.aws/docker/library/python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    flask gunicorn \
    "tabpfn>=2.0,<3.0" \
    pandas numpy scikit-learn

COPY inference.py /opt/program/inference.py

WORKDIR /opt/program

EXPOSE 8080

ENTRYPOINT ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "inference:app"]
