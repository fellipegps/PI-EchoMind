"""Exige 80% de linhas por módulo documental, usando o XML do gate global."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


# PRs 06, 07–10 e 13; inclui a barreira de upload extraída da borda da PR 15.
REQUIRED_MODULES = (
    "document_ingestion.py",
    "document_processing.py",
    "document_repository.py",
    "document_upload.py",
)
MINIMUM_PERCENT = 80


def _line_counts(source: ET.Element) -> tuple[int, int]:
    lines = source.findall("./lines/line")
    measured = {int(line.attrib["number"]): int(line.attrib["hits"]) for line in lines}
    if len(measured) != len(lines) or any(number <= 0 or hits < 0 for number, hits in measured.items()):
        raise ValueError("contagens de linhas inválidas")
    return sum(hits > 0 for hits in measured.values()), len(measured)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", type=Path, default=Path("coverage.xml"))
    args = parser.parse_args(argv)
    try:
        root = ET.parse(args.report).getroot()
    except (OSError, ET.ParseError) as exc:
        print(f"Não foi possível ler o relatório {args.report}: {exc}", file=sys.stderr)
        return 1

    failed = False
    for module in REQUIRED_MODULES:
        sources = [
            source for source in root.findall(".//class")
            if source.get("filename", "").replace("\\", "/") in (module, f"app/{module}")
        ]
        label = f"app/{module}"
        if not sources:
            print(f"{label}: módulo obrigatório ausente no relatório", file=sys.stderr)
            failed = True
            continue
        if len(sources) != 1:
            print(f"{label}: módulo duplicado no relatório", file=sys.stderr)
            failed = True
            continue
        try:
            covered, total = _line_counts(sources[0])
        except (KeyError, ValueError) as exc:
            print(f"{label}: relatório inválido ({exc})", file=sys.stderr)
            failed = True
            continue
        if total == 0:
            print(f"{label}: sem linhas executáveis no relatório", file=sys.stderr)
            failed = True
            continue
        passed = covered * 100 >= MINIMUM_PERCENT * total
        print(f"{label}: {covered}/{total} linhas ({covered / total * 100:.2f}%) — "
              f"{'OK' if passed else 'ABAIXO DE 80%'}")
        failed |= not passed
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
