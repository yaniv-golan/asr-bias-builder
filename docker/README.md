# Docker Usage

Build production image:

```bash
docker build -f docker/Dockerfile -t asr-bias-builder .
```

Development shell:

```bash
docker compose -f docker/docker-compose.yml run --rm asr-bias-builder
```
