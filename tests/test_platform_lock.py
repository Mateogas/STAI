"""Cross-platform installation lock contract."""

from stai.state import Repo


def test_installation_lock_works_on_the_host_platform(tmp_path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")

    with repo.installation_lock():
        assert repo.lock_path.exists()
