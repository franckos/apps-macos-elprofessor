import threading
import pytest
from core.database import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def profile(db):
    return db.create_profile("Franck", "🧑", {})


def test_concurrent_writes_do_not_corrupt(db, profile):
    """Two threads writing memories simultaneously must not raise or corrupt."""
    errors = []

    def write_memories():
        try:
            for i in range(20):
                db.create_memory(profile["id"], f"Memory {i}", ["perso"])
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=write_memories)
    t2 = threading.Thread(target=write_memories)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"Concurrent write errors: {errors}"
    memories = db.list_memories(profile["id"])
    assert len(memories) == 40
