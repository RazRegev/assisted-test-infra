import sys
import os
import json
from argparse import ArgumentParser
from filelock import FileLock


class IndexProvider(object):
    """ Provides lock-safe context for get, set and delete actions of unique
        indexes per namespaces. """

    def __init__(self, filepath, lock):
        self._filepath = filepath
        self._lock = lock
        self._in_context = False
        self._ns_to_idx = {}

    def __enter__(self):
        self._lock.acquire()
        self._in_context = True
        self._load()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._dump()

        self._ns_to_idx.clear()
        self._lock.release()
        self._in_context = False

    def _load(self):
        if not self._ensure_file_existence():
            self._ns_to_idx = {}
            return

        with open(self._filepath, 'r') as fp:
            try:
                self._ns_to_idx = json.load(fp)
            except json.JSONDecodeError:
                self._ns_to_idx = {}

    def _ensure_file_existence(self):
        if os.path.isfile(self._filepath):
            return True
        open(self._filepath, 'w').close()
        return False

    def _dump(self):
        with open(self._filepath, 'w') as fp:
            json.dump(self._ns_to_idx, fp)

    def set_index(self, ns, idx):
        if self._in_context is False:
            return
        self._ns_to_idx[ns] = idx

    def get_index(self, ns):
        return self._ns_to_idx.get(ns)

    def del_index(self, ns):
        return bool(self._ns_to_idx.pop(ns, None))

    def clear_all(self):
        self._ns_to_idx.clear()

    def first_unused_index(self):
        idx = 0
        for v in sorted(self._ns_to_idx.values()):
            if v > idx:
                return idx
            idx += 1
        return idx


_indexer = IndexProvider(
    filepath='build/namespaces-indexes.json',
    lock=FileLock('/tmp/namespaces-indexes.lock')
)


def set_idx(ns):
    with _indexer:
        idx = _indexer.get_index(ns)
        if idx is None:
            idx = _indexer.first_unused_index()
            _indexer.set_index(ns, idx)

    sys.stdout.write(str(idx))


def get_idx(ns):
    with _indexer:
        idx = _indexer.get_index(ns)

    if idx is None:
        sys.stderr.write(f'namespace {ns} does not exist\n')
        sys.exit(1)

    sys.stdout.write(str(idx))


def del_idx(ns):
    with _indexer:
        if ns == 'all':
            _indexer.clear_all()
            return
        ret = _indexer.del_index(ns)

    if not ret:
        sys.stderr.write(f'namespace {ns} does not exist\n')
        sys.exit(1)


actions_to_methods = {
    'set': set_idx,
    'get': get_idx,
    'del': del_idx
}


def main(action, namespace, oc_mode=False):
    if not os.path.isdir('build'):
        os.mkdir('build')

    if oc_mode:
        # Add a prefix to remote namespace to avoid conflicts in case local and
        # remote namespaces are having the same name.
        namespace = f'OC__{namespace}'

    actions_to_methods[action](namespace)


if __name__ == '__main__':
    parser = ArgumentParser(
        __file__,
        description='Use to get, set or delete a unique index for an '
                    'assisted-installer namespace. '
                    'This index will be used to allocate ports, cidr '
                    'ips and network bridges for each namespace.'
    )
    parser.add_argument(
        '-a', '--action',
        choices=['get', 'set', 'del'],
        required=True,
        help='Action to perform'
    )
    parser.add_argument(
        '-n', '--namespace',
        type=str,
        required=True,
        help='Target namespace'
    )
    parser.add_argument(
        '--oc-mode',
        action='store_true',
        default=False,
        help='Set if assisted-installer is running on PSI'
    )
    args = parser.parse_args()
    main(**args.__dict__)
