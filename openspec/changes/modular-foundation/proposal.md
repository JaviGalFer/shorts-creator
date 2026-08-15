# Proposal: modular-foundation

## Problem

El proyecto carece de empaquetado Python estructurado (`pyproject.toml`) y de paquete `src/`. Los módulos viven sueltos en `bin/` y `tests/` con paths de importación implícitos. Agentes y scripts externos no pueden importar `shorts_creator` como librería. Cada cambio futuro requiere reconfigurar `sys.path` manualmente. No hay boundaries claros entre dominios.

## Solution

Crear la base modular: `pyproject.toml` con layout `src`, paquete `shorts_creator` con subpaquetes `contracts` e `infrastructure` vacíos (scaffolding), y tests focales. Esto permite `pip install -e .` o `pythonpath=["src"]` para importar la librería sin tocar `bin/` ni el pipeline. El cambio es reversibel y no migra código funcional.

## Success Criteria

- `pyproject.toml` válido con setuptools + src layout
- `import shorts_creator` desde repo root (con pythonpath o instalado)
- `import shorts_creator.contracts` y `import shorts_creator.infrastructure` sin errores
- `python3 bin/run_job.py --help` sigue funcionando (exit 0)
- Suite completa mantiene `1181 passed, 0 failed`