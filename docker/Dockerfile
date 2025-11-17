FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt && pip install .

ENTRYPOINT ["python", "-m", "asr_bias_builder.cli"]
