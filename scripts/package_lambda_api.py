#!/usr/bin/env python3
"""Script de empaquetado reproducible para AWS Lambda (CDM-20 / CDM-119).

Genera un archivo ZIP autocontenido con el código fuente y las dependencias de
producción para Python 3.12 en arquitectura x86_64 (Linux manylinux2014).
Permite empaquetado cross-platform nativo sin requerir Docker gracias a `uv`.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
API_DIR = ROOT_DIR / "apps" / "api"
SRC_DIR = API_DIR / "src" / "cdm"
DEFAULT_OUTPUT = ROOT_DIR / "build" / "cdm-api-lambda.zip"


def export_requirements(output_file: Path) -> None:
    """Exporta las dependencias de producción fijadas en uv.lock."""
    cmd = [
        "uv",
        "export",
        "--directory",
        str(API_DIR),
        "--no-dev",
        "--no-emit-project",
        "--no-hashes",
        "-o",
        str(output_file),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def install_dependencies(requirements_file: Path, target_dir: Path, platform: str) -> None:
    """Instala las dependencias para la plataforma de destino de Lambda."""
    cmd = [
        "uv",
        "pip",
        "install",
        "-r",
        str(requirements_file),
        "--target",
        str(target_dir),
        "--python-platform",
        platform,
        "--python-version",
        "3.12",
        "--only-binary",
        ":all:",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback sin --only-binary si algún paquete puro no tiene wheel específico
        cmd_fallback = [
            "uv",
            "pip",
            "install",
            "-r",
            str(requirements_file),
            "--target",
            str(target_dir),
            "--python-platform",
            platform,
            "--python-version",
            "3.12",
        ]
        subprocess.run(cmd_fallback, check=True)


def create_zip(source_dir: Path, output_zip: Path) -> None:
    """Empaqueta el contenido del directorio en un archivo ZIP determinístico."""
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # Omitir cachés de Python
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.endswith(".dist-info")]
            for file in files:
                if file.endswith((".pyc", ".pyo")):
                    continue
                full_path = Path(root) / file
                archive_name = full_path.relative_to(source_dir)
                zf.write(full_path, archive_name)


def package(output_path: Path, code_only: bool = False, platform: str = "x86_64-manylinux2014") -> None:
    """Construye el artefacto ZIP final."""
    print(f"--> Empaquetando Lambda API en: {output_path}")
    with tempfile.TemporaryDirectory(prefix="cdm-lambda-build-") as temp_dir_str:
        build_dir = Path(temp_dir_str)

        # 1. Copiar código fuente de la aplicación (cdm)
        target_cdm = build_dir / "cdm"
        shutil.copytree(SRC_DIR, target_cdm, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        # 2. Instalar dependencias si no es un paquete code-only
        if not code_only:
            req_file = build_dir / "requirements.txt"
            print("--> Exportando dependencias de producción...")
            export_requirements(req_file)
            print(f"--> Instalando dependencias para {platform} (Python 3.12)...")
            install_dependencies(req_file, build_dir, platform)
            req_file.unlink(missing_ok=True)
        else:
            print("--> Modo code-only: omitiendo instalación de dependencias externas.")

        # 3. Crear ZIP final
        print("--> Generando archivo ZIP final...")
        create_zip(build_dir, output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"--> Paquete generado con éxito: {output_path} ({size_mb:.2f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Empaquetado de Lambda FastAPI CDM")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Ruta del archivo ZIP de salida (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--code-only",
        action="store_true",
        help="Empaquetar solo el código fuente cdm/ sin dependencias (ideal para validación local rápida)",
    )
    parser.add_argument(
        "--platform",
        default="x86_64-manylinux2014",
        help="Plataforma de destino para wheels binarios (default: x86_64-manylinux2014)",
    )

    args = parser.parse_args()
    package(args.output, code_only=args.code_only, platform=args.platform)


if __name__ == "__main__":
    main()
