# Tareas: Bootstrap

## Fundación documental

- [x] Crear estructura de directorios
- [x] Crear .gitignore
- [x] Crear .env.example
- [x] Crear docker-compose.yml
- [x] Crear AGENTS.md
- [x] Crear docs/project/vision.md
- [x] Crear docs/project/architecture.md
- [x] Crear docs/project/integrations.md
- [x] Crear docs/project/glossary.md
- [x] Crear docs/project/roadmap.md
- [x] Crear docs/project/environment.md
- [x] Crear docs/project/cost-model.md
- [x] Crear docs/project/security.md
- [x] Crear ADR-0001 (project-scope)
- [x] Crear docs/sessions/README.md
- [x] Crear docs/sessions/2026-06-29-2100-bootstrap-inicial.md
- [x] Crear docs/runbooks/ (local, render, n8n)

## OpenSpec

- [x] Crear openspec/project.md
- [x] Crear openspec/changes/bootstrap-video-automation/proposal.md
- [x] Crear openspec/changes/bootstrap-video-automation/design.md
- [x] Crear openspec/changes/bootstrap-video-automation/tasks.md
- [x] Crear openspec/changes/bootstrap-video-automation/specs/project-foundation.md

## Agentes y skills

- [x] Crear .opencode/agents/ (5 agentes)
- [x] Crear .opencode/skills/ (7 skills)

## Data

- [x] Crear directorios data/ con .gitkeep
- [x] Crear logs/.gitkeep

## Validación final

- [x] Revisar que ningún secreto está versionado (docker-compose usa ${VAR}, .env gitignorado, credential-*.json añadido a .gitignore)
- [x] Revisar que .gitignore cubre todos los directorios de datos (data/assets, audio, subtitles, renders, metadata, logs)
- [x] Revisar que docker-compose.yml levanta sin errores (docker-compose config válido)
- [x] Confirmar estructura completa con `tree` (verificada con find)
