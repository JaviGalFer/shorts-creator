# Tareas: modular-foundation

## T1 — Crear pyproject.toml
- [x] `[build-system]` setuptools + wheel
- [x] `[project]` name=shorts-creator version=0.1.0 python-requires=">=3.10"`
- [x] `[tool.setuptools.packages.find] where=["src"]`
- [x] `[tool.pytest.ini_options] pythonpath = ["src"]`

## T2 — Crear `src/shorts_creator/__init__.py`
- [x]`__version__ = "0.1.0"`
- [x] docstring corta

## T3 — Scaffolding `contracts/` e `infrastructure/`
- [x] `src/shorts_creator/contracts/__init__.py` — importable, docstring "contractos compartidos V2"
- [x] `src/shorts_creator/infrastructure/__init__.py` — importable, docstring "implementación técnica V2"

## T4 — Crear `tests/test_modular_foundation.py`
- [x] `import shorts_creator` → assert presente
- [x] `shorts_creator.__version__ == "0.1.0"`
- [x] `shorts_creator.__file__` contiene `"src/shorts_creator"`
- [x] `from shorts_creator.contracts import ...` → assert importable
- [x] `from shorts_creator.infrastructure import ...` → assert importable
- [x] `import subprocess; subprocess.run(["python3", "bin/run_job.py", "--help"]); assert exit_code == 0`

## T5 — Ejecutar suite completa
- [x] `python -m pytest tests/ -q` — mantener `1186 passed, 0 failed`

## T6 — Cierre y documentación interna
- [x] validar `git diff --check` (whitespace)
- [x] validar `git status` — solo archivos previstos modificados/creados

Review read-only focalizado al cierre.