#!/usr/bin/env python3
"""Script de empaquetado y publicación del frontend Angular en S3 + CloudFront (CDM-23 / CDM-79 / CDM-80).

Construye la SPA Angular para el entorno solicitado, valida los artefactos
generados y aplica las políticas de caché recomendadas:
  - index.html: no-cache, no-store, must-revalidate (HTML fresco siempre).
  - Assets con hash (*.js, *.css): public, max-age=31536000, immutable (1 año de caché).

Uso:
    python scripts/deploy_frontend.py --configuration production --dry-run
    python scripts/deploy_frontend.py --bucket cdm-dev-web-xxxx --distribution-id E123456
"""

from __future__ import annotations

import argparse
import mimetypes
import shutil
import subprocess
import sys
from pathlib import Path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construye y despliega la SPA Angular en S3 + CloudFront."
    )
    parser.add_argument(
        "--configuration",
        default="production",
        choices=["production", "development"],
        help="Configuración de Angular a compilar (default: production).",
    )
    parser.add_argument(
        "--bucket",
        default="",
        help="Nombre del bucket S3 de destino.",
    )
    parser.add_argument(
        "--distribution-id",
        default="",
        help="ID de distribución CloudFront para invalidación de caché.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Omite el paso de compilación si dist ya está generado.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta la validación y empaquetado sin realizar llamadas de red a AWS.",
    )
    return parser.parse_args()


def resolve_paths() -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parent.parent
    web_dir = repo_root / "apps" / "web"
    dist_dir = web_dir / "dist" / "web" / "browser"

    if not dist_dir.exists():
        # Fallback para estructuras donde la salida es dist/web directamente
        alt_dist = web_dir / "dist" / "web"
        if alt_dist.exists() and (alt_dist / "index.html").exists():
            dist_dir = alt_dist

    return web_dir, dist_dir


def build_angular(web_dir: Path, configuration: str) -> None:
    print(f"[*] Compilando Angular en {web_dir} con configuración '{configuration}'...")
    pnpm_executable = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if not pnpm_executable:
        raise RuntimeError("No se encontró pnpm en el PATH del sistema.")

    cmd = [pnpm_executable, "run", "build", f"--configuration={configuration}"]
    result = subprocess.run(cmd, cwd=web_dir, capture_output=True, text=True)

    if result.returncode != 0:
        print("[!] Error en la compilación de Angular:\n", result.stderr, file=sys.stderr)
        raise RuntimeError(f"Fallo en la compilación con código {result.returncode}")

    print("[✓] Compilación de Angular completada exitosamente.")


def validate_artifacts(dist_dir: Path) -> list[Path]:
    if not dist_dir.exists():
        raise FileNotFoundError(f"El directorio de artefactos {dist_dir} no existe.")

    index_file = dist_dir / "index.html"
    if not index_file.exists():
        raise FileNotFoundError(f"No se encontró index.html en {dist_dir}.")

    files = [f for f in dist_dir.rglob("*") if f.is_file()]
    if not files:
        raise RuntimeError("El directorio de compilación está vacío.")

    total_bytes = sum(f.stat().st_size for f in files)
    print(f"[✓] Artefactos validados: {len(files)} archivos ({total_bytes / 1024:.2f} KB).")
    for f in sorted(files):
        rel = f.relative_to(dist_dir)
        size_kb = f.stat().st_size / 1024
        print(f"    - {rel} ({size_kb:.1f} KB)")

    return files


def upload_to_s3(dist_dir: Path, bucket: str, dry_run: bool) -> None:
    aws_cli = shutil.which("aws") or shutil.which("aws.cmd")
    if not aws_cli:
        print("[!] Advertencia: AWS CLI no encontrado. Omitiendo sincronización S3.")
        return

    # 1. Subir assets con hash (1 año de caché inmutable)
    print(f"[*] Sincronizando assets inmutables a s3://{bucket}...")
    cmd_assets = [
        aws_cli,
        "s3",
        "sync",
        str(dist_dir),
        f"s3://{bucket}",
        "--exclude",
        "index.html",
        "--cache-control",
        "public, max-age=31536000, immutable",
        "--delete",
    ]
    if dry_run:
        cmd_assets.append("--dryrun")
    subprocess.run(cmd_assets, check=True)

    # 2. Subir index.html (sin caché para forzar recarga en actualizaciones)
    print(f"[*] Subiendo index.html a s3://{bucket} (no-cache)...")
    cmd_index = [
        aws_cli,
        "s3",
        "cp",
        str(dist_dir / "index.html"),
        f"s3://{bucket}/index.html",
        "--cache-control",
        "no-cache, no-store, must-revalidate",
        "--content-type",
        "text/html",
    ]
    if dry_run:
        cmd_index.append("--dryrun")
    subprocess.run(cmd_index, check=True)

    print(f"[✓] Despliegue en s3://{bucket} completado.")


def invalidate_cloudfront(distribution_id: str, dry_run: bool) -> None:
    if not distribution_id:
        return

    if dry_run:
        print(f"[*] [dry-run] Invalidación de CloudFront para {distribution_id}: /*")
        return

    aws_cli = shutil.which("aws") or shutil.which("aws.cmd")
    if not aws_cli:
        print("[!] Advertencia: AWS CLI no encontrado. Omitiendo invalidación de CloudFront.")
        return

    print(f"[*] Invalidando caché de CloudFront para distribución {distribution_id}...")
    cmd = [
        aws_cli,
        "cloudfront",
        "create-invalidation",
        "--distribution-id",
        distribution_id,
        "--paths",
        "/*",
    ]
    subprocess.run(cmd, check=True)
    print("[✓] Invalidación de CloudFront solicitada.")


def main() -> int:
    args = parse_arguments()
    web_dir, dist_dir = resolve_paths()

    try:
        if not args.skip_build:
            build_angular(web_dir, args.configuration)
            # Re-resolver ruta tras la compilación
            _, dist_dir = resolve_paths()

        validate_artifacts(dist_dir)

        if args.bucket:
            upload_to_s3(dist_dir, args.bucket, args.dry_run)
            invalidate_cloudfront(args.distribution_id, args.dry_run)
        elif args.dry_run:
            print("[✓] Modo dry-run completado sin publicar en AWS.")
        else:
            print("[i] No se proporcionó --bucket. Solo se generaron los artefactos locales.")

        return 0
    except Exception as exc:
        print(f"[!] Error en el despliegue del frontend: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
