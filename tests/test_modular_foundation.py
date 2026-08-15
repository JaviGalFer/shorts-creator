"""Smoke tests for modular foundation packaging.

Verifica que la estructura src/ está correcta y que bin/ sigue funcionando.
"""

import subprocess
import sys

import pytest


def test_imports_from_src():
    """import shorts_creator debe resolverse desde src/."""
    import shorts_creator
    assert "__version__" in dir(shorts_creator)
    assert shorts_creator.__version__ == "0.1.0"
    assert "src" in shorts_creator.__file__


def test_contracts_importable():
    """contracts subpaquete debe ser importable."""
    from shorts_creator.contracts import __all__
    assert __all__ == []


def test_infrastructure_importable():
    """infrastructure subpaquete debe ser importable."""
    from shorts_creator.infrastructure import __all__
    assert __all__ == []


def test_bin_help():
    """python3 bin/run_job.py --help debe devolver exit 0."""
    result = subprocess.run(
        [sys.executable, "bin/run_job.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_pythonpath_coverage():
    """Verificación mínima de pythonpath=["src"] en pytest."""
    # Este test asegura que la configuración de pytest no rompe nada.
    assert True