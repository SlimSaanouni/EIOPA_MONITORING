import importlib
from pathlib import Path

from eiopa_rfr import paths as paths_module


def _reload_with_env(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("COCKPIT_STUDY_DIR", raising=False)
    else:
        monkeypatch.setenv("COCKPIT_STUDY_DIR", value)
    return importlib.reload(paths_module)


def test_cockpit_study_dir_takes_priority(monkeypatch, tmp_path):
    """COCKPIT_STUDY_DIR, posée par le Cockpit, doit primer sur find_repo_root(),
    et BASE_DIR doit pointer vers le sous-dossier propre à ce module (pas la
    racine de l'étude, partagée avec slim/esg/asset_ptf)."""
    study_dir = tmp_path / "etude_active"
    reloaded = _reload_with_env(monkeypatch, str(study_dir))
    try:
        assert reloaded.BASE_DIR == study_dir.resolve() / "eiopa_rfr"
    finally:
        _reload_with_env(monkeypatch, None)


def test_cockpit_study_dir_expands_user(monkeypatch, tmp_path):
    """La valeur est passée par expanduser()/resolve() (ex. chemin relatif ou ~)."""
    reloaded = _reload_with_env(monkeypatch, str(tmp_path) + "/../" + tmp_path.name)
    try:
        assert reloaded.BASE_DIR == tmp_path.resolve() / "eiopa_rfr"
    finally:
        _reload_with_env(monkeypatch, None)


def test_without_cockpit_study_dir_falls_back_to_repo_root(monkeypatch):
    """Sans la variable, comportement inchangé : find_repo_root() (ou platformdirs)."""
    reloaded = _reload_with_env(monkeypatch, None)
    expected = reloaded.find_repo_root() or Path(
        __import__("platformdirs").user_data_dir("eiopa-rfr", appauthor=False)
    )
    assert reloaded.BASE_DIR == expected
