#!/usr/bin/env python
from multiprocessing import Pool, TimeoutError
from dulwich.client import get_transport_and_path
from dulwich.repo import MemoryRepo
from dulwich.object_store import MemoryObjectStore
from dulwich.objects import Commit

RETRY_DEPTH = 32


class TreelessObjectStore(MemoryObjectStore):
    def add_object(self, obj):
        if isinstance(obj, Commit):
            self._data[obj.id] = obj.copy()


def _do_fetch(url, ref, depth=None):
    repo = MemoryRepo()
    repo.object_store = TreelessObjectStore()
    client, path = get_transport_and_path(url)
    client.fetch(path, repo, depth=depth)
    return repo[ref]


def timelimit(t, fn, *args, **kwargs):
    with Pool(processes=1) as pool:
        return pool.apply_async(fn, *args, **kwargs).get(timeout=t)


def fetch_commit(url, sha):
    sha = sha.encode('ascii')
    try:
        return timelimit(30, _do_fetch, (url, sha))
    except TimeoutError as e:
        return timelimit(20, _do_fetch, (url, sha), {'depth': RETRY_DEPTH})


if __name__ == '__main__':
    import sys
    url, sha = sys.argv[1:]
    commit = fetch_commit(url, sha)
    print(commit.message)
