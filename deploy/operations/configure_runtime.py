"""Validate/install private production config without echoing secret values.

Run on the Linux host. This tool never fetches AWS secrets or contacts services.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import re
import stat
import tempfile


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "runtime_config", ROOT / "echomind-backend/app/runtime_config.py",
)
runtime_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime_config)


class PrivateConfigurationError(ValueError):
    pass


def parse_raw(contents: str) -> dict[str, str]:
    """Same unquoted single-line subset used by our Compose raw env_file."""
    result: dict[str, str] = {}
    for line in contents.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if (not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name)
                or name in result or "\0" in value or value.startswith(("'", '"'))):
            raise PrivateConfigurationError("Formato inválido; use NAME=value sem aspas ou duplicatas.")
        result[name] = value
    return result


DEFAULTS = parse_raw((ROOT / "deploy/.env.example").read_text(encoding="utf-8"))
ALLOWED = DEFAULTS.keys() | {
    "RERANKER_MODEL", "RERANKER_CANDIDATE_LIMIT", "RERANKER_MAX_CHARS", "RERANKER_TIMEOUT_SECONDS",
}


def outside_checkout(path: Path) -> Path:
    absolute = path.absolute()
    if any(parent.is_symlink() for parent in (absolute, *absolute.parents)):
        raise PrivateConfigurationError("O caminho privado não pode conter links simbólicos.")
    resolved = absolute.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise PrivateConfigurationError("O arquivo privado deve ficar fora do repositório.")
    return resolved


def check_permissions(metadata: os.stat_result, *, directory: bool = False) -> None:
    if os.name != "posix":
        return
    if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
        raise PrivateConfigurationError("Exija proprietário atual e permissões 600 (arquivo) ou 700 (diretório).")
    if directory and not stat.S_ISDIR(metadata.st_mode):
        raise PrivateConfigurationError("O diretório privado é inválido.")


def read_private_file(path: Path) -> dict[str, str]:
    path = outside_checkout(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "r", encoding="utf-8") as source:
        metadata = os.fstat(source.fileno())
        check_permissions(metadata)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 65536:
            raise PrivateConfigurationError("Arquivo privado inválido ou maior que 64 KiB.")
        return parse_raw(source.read(65537))


def validated_config(values: dict[str, str]) -> dict[str, str]:
    unknown = values.keys() - ALLOWED
    if unknown:
        raise PrivateConfigurationError("Arquivo contém variáveis não previstas no exemplo de produção.")
    result = DEFAULTS | values
    if any(any(char in value for char in "\r\n\0") for value in result.values()):
        raise PrivateConfigurationError("Valores devem ocupar uma única linha.")
    if result["ECHOMIND_ENV"] != "production":
        raise PrivateConfigurationError("ECHOMIND_ENV deve ser production.")
    runtime_config.validate_production(result)
    return result


def install_private_file(path: Path, values: dict[str, str], *, replace: bool = False) -> None:
    values = validated_config(values)
    if os.name != "posix":
        raise PrivateConfigurationError("A instalação com permissões restritas deve ser executada no host Linux.")
    path = outside_checkout(path)
    path.parent.mkdir(mode=0o700, parents=False, exist_ok=True)
    check_permissions(path.parent.stat(), directory=True)
    if path.exists():
        if not replace:
            raise PrivateConfigurationError("Destino já existe; use --replace para uma rotação explícita.")
        check_permissions(path.stat())
    descriptor, temporary = tempfile.mkstemp(prefix=".backend-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
            os.fchmod(destination.fileno(), 0o600)
            for name, value in values.items():
                # Environment input must be just as safe as raw file input.
                if any(char in value for char in "\r\n\0"):
                    raise PrivateConfigurationError("Valores devem ocupar uma única linha.")
                destination.write(f"{name}={value}\n")
            destination.flush()
            os.fsync(destination.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            # Atomic no-clobber publication, including concurrent installers.
            os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Arquivo privado fora do checkout")
    source.add_argument("--from-environment", action="store_true", help="Receber valores do processo pai, incluindo asm-exec")
    parser.add_argument("--output", type=Path, help="Instalar no host Linux; omita para apenas validar")
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    try:
        values = ({name: os.environ[name] for name in ALLOWED if name in os.environ}
                  if arguments.from_environment else read_private_file(arguments.file))
        values = validated_config(values)
        if arguments.output:
            install_private_file(arguments.output, values, replace=arguments.replace)
        print("Configuração de produção validada" + (" e instalada com acesso restrito." if arguments.output else "."))
        if os.name != "posix":
            print("Permissões de arquivo precisam ser verificadas no Linux antes da publicação.")
        return 0
    except (PrivateConfigurationError, runtime_config.ProductionConfigurationError) as error:
        print(str(error))
    except (OSError, UnicodeError, ValueError):
        print("Não foi possível ler ou instalar a configuração privada; verifique formato, caminhos e permissões.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
