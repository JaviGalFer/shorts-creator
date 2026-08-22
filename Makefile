SHELL := /bin/bash
DOCKER_COMPOSE := docker-compose

OPENCODE_HOST ?= 127.0.0.1
OPENCODE_PORT ?= 4096

.DEFAULT_GOAL := help

.PHONY: help doctor docker-up docker-down docker-logs stack-up stack-down opencode test

help:
	@printf "Targets disponibles:\n"
	@printf "  make doctor         - Valida prerequisitos locales\n"
	@printf "  make docker-up      - Levanta n8n + postgres\n"
	@printf "  make docker-down    - Detiene contenedores\n"
	@printf "  make docker-logs    - Sigue logs de n8n\n"
	@printf "  make opencode       - Inicia opencode web\n"
	@printf "  make stack-up       - Levanta docker + opencode\n"
	@printf "  make stack-down     - Baja stack docker\n"
	@printf "  make test           - Valida estructura del proyecto\n"

doctor:
	@echo "=== Doctor: Shorts Creator ==="; \
	status=0; \
	if command -v docker >/dev/null 2>&1; then echo "[OK] docker"; else echo "[ERR] docker"; status=1; fi; \
	if command -v $(DOCKER_COMPOSE) >/dev/null 2>&1; then echo "[OK] $(DOCKER_COMPOSE)"; else echo "[ERR] $(DOCKER_COMPOSE)"; status=1; fi; \
	if command -v ffmpeg >/dev/null 2>&1; then echo "[OK] ffmpeg"; else echo "[WARN] ffmpeg no instalado (puedes usar contenedor Docker)"; fi; \
	if [ -f .env ]; then echo "[OK] .env presente"; else echo "[WARN] .env no encontrado (copia .env.example)"; fi; \
	if [ $$status -eq 0 ]; then echo "=== Estado: OK ==="; else echo "=== Estado: ERRORES ==="; exit 1; fi

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f n8n

opencode:
	opencode web --hostname "$(OPENCODE_HOST)" --port "$(OPENCODE_PORT)"

stack-up: docker-up opencode

stack-down: docker-down

test:
	@echo "=== Validación de estructura ==="; \
	errors=0; \
	for d in docs/project docs/decisions docs/sessions docs/runbooks openspec openspec/changes/bootstrap-video-automation/specs .opencode/agents .opencode/skills data/assets data/audio data/subtitles data/renders data/metadata logs; do \
		if [ -d "$$d" ]; then echo "[OK] $$d"; else echo "[ERR] $$d"; errors=$$((errors+1)); fi; \
	done; \
	for f in AGENTS.md .env.example .gitignore docker-compose.yml openspec/project.md; do \
		if [ -f "$$f" ]; then echo "[OK] $$f"; else echo "[ERR] $$f"; errors=$$((errors+1)); fi; \
	done; \
	if [ $$errors -eq 0 ]; then echo "=== Estructura OK ==="; else echo "=== $$errors errores ==="; exit 1; fi

backend-up:
	PYTHONPATH=src python3 -m uvicorn shorts_creator.web.app:app --host 127.0.0.1 --port 8000 --workers 1
