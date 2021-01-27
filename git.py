#!/usr/bin/env python
from dulwich.client import get_transport_and_path
from dulwich.repo import MemoryRepo
from dulwich.object_store import MemoryObjectStore
from dulwich.objects import Commit

RETRY_DEPTH = 32


class TreelessObjectStore(MemoryObjectStore):
    def add_object(self, obj):
        if isinstance(obj, Commit):
            self._data[obj.id] = obj.copy()


def fetch_commit(url, sha):
    repo = MemoryRepo()
    repo.object_store = TreelessObjectStore()
    client, path = get_transport_and_path(url)
    client.fetch(path, repo)
    return repo[sha.encode('ascii')]


if __name__ == '__main__':
    import sys
    url, sha = sys.argv[1:]
    commit = fetch_commit(url, sha)
    print(commit.message)
