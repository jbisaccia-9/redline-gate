import pytest

from redlinegate import loop, seed


@pytest.fixture(scope="session")
def jobs(tmp_path_factory):
    root = tmp_path_factory.mktemp("rg")
    seed.write(root / "data")
    for job in seed.JOBS:
        loop.run_job(root / "data", job, root / "jobs")
    return root
