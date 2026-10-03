from pathlib import Path


def test_protocol_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "EXPERIMENT.md").exists()
    assert (root / "CLAUDE.md").exists()
    assert (root / "prompts" / "01_build_world.md").exists()
