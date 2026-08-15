# Diseño: modular-foundation

## Archivos afectados

### Nueva estructura

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `pyproject.toml` | build-system | setuptools, src layout, python>=3.10, pythonpath=["src"] para tests |
| `src/shorts_creator/__init__.py` | package | `__version__="0.1.0"` |
| `src/shorts_creator/contracts/__init__.py` | scaffold | vacío, importable, docstring |
| `src/shorts_creator/infrastructure/__init__.py` | scaffold | vacío, importable, docstring |
| `tests/test_modular_foundation.py` | test | smoke packaging |

### Sin cambios

- `bin/` sin modificar — scripts siguen ejecutándose como antes
- `requirements.txt` sin mover — sigue siendo fuente canónica de deps
- Sin entry points, renombrados ni lógica funcional

### Contrato de importación

```
import shorts_creator          # desde src/ o pythonpath=["src"]
import shorts_creator.contracts  # scaffold vacío
import shorts_creator.infrastructure  # scaffold vacío
```

## Orden de ejecución por slice

1. Crear `pyproject.toml` (build config)
2. Esbozar `src/shorts_creator/` con `__init__.py`
3. Scaffolding `contracts/` e `infrastructure/` `__init__.py`
4. Crear `tests/test_modular_foundation.py`
5. Verificar `python3 bin/run_job.py --help` (exit 0)
6. Ejecutar suite completa — mantener baseline `1181 passed, 0 failed`