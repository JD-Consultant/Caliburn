"""Public occupation sources remain independent of Workspace reference mappings."""

from pathlib import Path

from tests.unit.test_import_boundaries import check_imports


def test_public_sources_do_not_depend_on_workspace_reference_mappings(
    tmp_path: Path,
) -> None:
    result = check_imports(
        tmp_path,
        "modules/occupation_reference/application/search.py",
        "\nfrom caliburn.modules.model_references import contracts\n",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert (
        "Occupation reference owns public sources "
        "without Agent or employee state BROKEN" in result.stdout
    )
