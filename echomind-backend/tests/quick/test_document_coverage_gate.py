"""Gate documental: cobertura de linhas, sem arredondar a decisão."""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scripts import check_document_coverage as gate


def report(tmp_path, *, covered=8, total=10, missing=None, prefix="", line_rate="0.8"):
    root = ET.Element("coverage", {"line-rate": line_rate})
    classes = ET.SubElement(ET.SubElement(ET.SubElement(root, "packages"), "package"), "classes")
    for module in gate.REQUIRED_MODULES:
        if module == missing:
            continue
        source = ET.SubElement(classes, "class", {"filename": prefix + module, "line-rate": line_rate})
        lines = ET.SubElement(source, "lines")
        for number in range(1, total + 1):
            ET.SubElement(lines, "line", {"number": str(number), "hits": "1" if number <= covered else "0"})
    path = tmp_path / "coverage.xml"
    ET.ElementTree(root).write(path, encoding="utf-8")
    return path


def test_required_modules_are_explicit_and_complete():
    assert gate.REQUIRED_MODULES == (
        "document_ingestion.py", "document_processing.py",
        "document_repository.py", "document_upload.py",
    )


def test_accepts_exactly_eighty_percent(tmp_path, capsys):
    assert gate.main([str(report(tmp_path))]) == 0
    output = capsys.readouterr().out
    for module in gate.REQUIRED_MODULES:
        assert f"app/{module}: 8/10 linhas (80.00%)" in output


def test_rejects_less_than_eighty_even_if_xml_rate_rounds_up(tmp_path, capsys):
    path = report(tmp_path, covered=7999, total=10000, line_rate="0.8")
    assert gate.main([str(path)]) == 1
    assert "79.99%" in capsys.readouterr().out


def test_cannot_compensate_one_module_with_other_modules_coverage(tmp_path):
    path = report(tmp_path, covered=10)
    tree = ET.parse(path)
    lines = tree.getroot().findall(".//class")[0].findall("./lines/line")
    for line in lines[7:]:
        line.set("hits", "0")
    tree.write(path)
    assert gate.main([str(path)]) == 1


@pytest.mark.parametrize("missing", [
    "document_ingestion.py", "document_processing.py", "document_repository.py", "document_upload.py",
])
def test_rejects_any_missing_required_module(tmp_path, capsys, missing):
    assert gate.main([str(report(tmp_path, missing=missing))]) == 1
    assert f"app/{missing}: módulo obrigatório ausente" in capsys.readouterr().err


@pytest.mark.parametrize("prefix", ["app/", "app\\"])
def test_accepts_report_paths_from_backend_root(tmp_path, prefix):
    assert gate.main([str(report(tmp_path, prefix=prefix))]) == 0


def test_does_not_accept_a_different_module_with_same_basename(tmp_path, capsys):
    assert gate.main([str(report(tmp_path, prefix="unrelated/"))]) == 1
    assert "módulo obrigatório ausente" in capsys.readouterr().err


def test_rejects_module_without_measured_lines(tmp_path, capsys):
    assert gate.main([str(report(tmp_path, total=0))]) == 1
    assert "sem linhas executáveis" in capsys.readouterr().err


@pytest.mark.parametrize("contents", [None, "<coverage>"])
def test_rejects_missing_or_invalid_report(tmp_path, capsys, contents):
    path = tmp_path / "absent.xml"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")
    assert gate.main([str(path)]) == 1
    assert "Não foi possível ler o relatório" in capsys.readouterr().err


def test_cli_returns_failure_status_for_undercovered_module(tmp_path):
    script = Path(__file__).parents[2] / "scripts" / "check_document_coverage.py"
    result = subprocess.run(
        [sys.executable, str(script), str(report(tmp_path, covered=7))],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "70.00%" in result.stdout


def test_rejects_duplicate_module_instead_of_choosing_better_coverage(tmp_path, capsys):
    path = report(tmp_path)
    tree = ET.parse(path)
    classes = tree.getroot().find("./packages/package/classes")
    classes.append(ET.fromstring(ET.tostring(classes[0])))
    tree.write(path)
    assert gate.main([str(path)]) == 1
    assert "módulo duplicado" in capsys.readouterr().err


@pytest.mark.parametrize("number,hits", [("1", "invalid"), ("1", "-1"), ("0", "1"), ("2", "1")])
def test_rejects_invalid_line_counts(tmp_path, capsys, number, hits):
    path = report(tmp_path)
    tree = ET.parse(path)
    line = tree.getroot().find(".//line")
    line.set("number", number)
    line.set("hits", hits)
    tree.write(path)
    assert gate.main([str(path)]) == 1
    assert "relatório inválido" in capsys.readouterr().err
