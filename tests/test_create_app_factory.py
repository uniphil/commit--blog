import os
from contextlib import contextmanager
from commitblog import create_app


@contextmanager
def environ(env):
    env_before = os.environ.copy()
    os.environ.update(env)
    try:
        yield
    finally:
        for k in env:
            del os.environ[k]
        os.environ.update(env_before)


def test_config():
    assert create_app().testing is False
    # config can be passed in directly
    assert create_app({'TESTING': True}).testing is True
    # or via the environment
    with environ({'TESTING': '1'}):
        assert create_app().testing is True
    # (just make sure the helper didn't actually mess things up)
    assert create_app().testing is False
