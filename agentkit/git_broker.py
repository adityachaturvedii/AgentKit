"""Trusted local Git broker for controller-created disposable repositories."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess


class GitBrokerError(ValueError):
    pass


OID = re.compile(r'^[0-9a-f]{40,64}$')
SAFE = re.compile(r'^[A-Za-z0-9._/-]+$')
EMAIL = re.compile(r'^[^\s<>@]+@[^\s<>@]+$')


@dataclass(frozen=True)
class GitIdentity:
    """Controller-owned identity for commits created during one broker run."""

    name: str
    email: str
    source: str

    def __post_init__(self):
        if (type(self.name) is not str or not self.name.strip() or self.name != self.name.strip() or
                len(self.name) > 200 or any(ord(character) < 32 for character in self.name) or
                '<' in self.name or '>' in self.name):
            raise GitBrokerError('invalid Git identity name')
        if (type(self.email) is not str or len(self.email) > 254 or
                not EMAIL.fullmatch(self.email)):
            raise GitBrokerError('invalid Git identity email')
        if (type(self.source) is not str or not self.source or len(self.source) > 100 or
                not re.fullmatch(r'[A-Za-z0-9._-]+', self.source)):
            raise GitBrokerError('invalid Git identity source')


DEFAULT_IDENTITY = GitIdentity('AgentKit Controller', 'controller@localhost',
                               'controller-default')


class GitBroker:
    def __init__(self, managed_root, *, identity=None):
        if identity is None:
            identity = DEFAULT_IDENTITY
        if not isinstance(identity, GitIdentity):
            raise GitBrokerError('trusted GitIdentity is required')
        self.identity = identity
        self.root = Path(managed_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.repositories = self.root / 'repositories'
        self.worktrees = self.root / 'worktrees'
        self.worker_copies = self.root / 'worker-copies'
        self.review_copies = self.root / 'review-copies'
        for path in (self.repositories, self.worktrees, self.worker_copies, self.review_copies):
            path.mkdir(exist_ok=True, mode=0o700)

    def _inside(self, path, parent=None):
        path = Path(path).resolve()
        parent = (parent or self.root).resolve()
        if path == parent or parent not in path.parents:
            raise GitBrokerError('path escapes managed root')
        return path

    def _git(self, repository, *args, cwd=None):
        return self._git_bytes(repository, *args, cwd=cwd).decode('utf-8', 'strict').strip()

    def _git_bytes(self, repository, *args, cwd=None):
        repository = self._inside(repository, self.repositories)
        argv = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false',
                '-c', 'core.quotePath=false',
                '-C', str(repository), *args]
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'LC_ALL')}
        env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                   GIT_AUTHOR_NAME=self.identity.name, GIT_AUTHOR_EMAIL=self.identity.email,
                   GIT_COMMITTER_NAME=self.identity.name, GIT_COMMITTER_EMAIL=self.identity.email)
        run = subprocess.run(argv, cwd=str(cwd or repository), env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=20, check=False)
        if run.returncode:
            raise GitBrokerError(run.stderr.decode('utf-8', 'replace'))
        return run.stdout

    def create_repository(self, name, files):
        records = {path: {'content': content.encode('utf-8'), 'mode': '100644'}
                   for path, content in files.items()}
        return self.create_repository_snapshot(name, records,
                                               message='Seed disposable fixture')

    def create_repository_snapshot(self, name, files, *, message):
        """Create an independent repository from validated bytes and regular-file modes."""
        if not SAFE.fullmatch(name) or '/' in name:
            raise GitBrokerError('invalid repository name')
        if not isinstance(files, dict) or not files:
            raise GitBrokerError('repository snapshot must contain files')
        repository = self.repositories / name
        if repository.exists() or repository.is_symlink():
            raise GitBrokerError('repository already exists')
        repository.mkdir(mode=0o700)
        environment = {key: value for key, value in os.environ.items()
                       if key in ('PATH', 'LANG', 'LC_ALL')}
        environment.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git', '-c', 'init.templateDir=', 'init', '-b', 'main', str(repository)],
                       env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, timeout=20)
        for relative, record in files.items():
            if (not isinstance(record, dict) or set(record) != {'content', 'mode'} or
                    not isinstance(record['content'], bytes) or
                    record['mode'] not in ('100644', '100755')):
                raise GitBrokerError('invalid repository snapshot entry')
            target = self._safe_relative(repository, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(record['content'])
            target.chmod(0o755 if record['mode'] == '100755' else 0o644)
        self._git(repository, 'add', '--', *sorted(files))
        self._git(repository, 'commit', '-m', message)
        return repository, self.revision(repository, 'HEAD')

    def _safe_relative(self, root, relative):
        if (not isinstance(relative, str) or not relative or len(relative.encode('utf-8')) > 4096 or
                '\x00' in relative or any(ord(character) < 32 for character in relative)):
            raise GitBrokerError('invalid relative path')
        parts = PurePosixPath(relative).parts
        if (PurePosixPath(relative).is_absolute() or not parts or
                any(part in ('', '.', '..', '.git') for part in parts) or
                str(PurePosixPath(relative)) != relative):
            raise GitBrokerError('invalid relative path')
        target = (Path(root) / relative).resolve()
        root = Path(root).resolve()
        if root not in target.parents or target == root:
            raise GitBrokerError('path traversal')
        return target

    def revision(self, repository, revision):
        value = self._git(repository, 'rev-parse', '--verify', revision + '^{commit}')
        if not OID.fullmatch(value):
            raise GitBrokerError('invalid Git revision')
        return value

    def create_task_worktree(self, repository, task_id, base_revision):
        base = self.revision(repository, base_revision)
        branch = 'agentkit/' + task_id
        if not SAFE.fullmatch(branch):
            raise GitBrokerError('invalid branch')
        worktree = self.worktrees / task_id
        if worktree.exists() or worktree.is_symlink():
            raise GitBrokerError('worktree already exists')
        self._git(repository, 'worktree', 'add', '-b', branch, str(worktree), base)
        return branch, worktree, base

    def _tracked(self, repository, revision):
        text = self._git(repository, 'ls-tree', '-r', '--name-only', revision)
        return [line for line in text.splitlines() if line]

    def export_snapshot(self, repository, revision, destination, *, review=False,
                        controlled_root=None):
        revision = self.revision(repository, revision)
        destination = Path(destination).resolve()
        if controlled_root is not None:
            if not review:
                raise GitBrokerError('external controlled roots are review-only')
            expected_parent = Path(controlled_root).resolve()
            temporary_root = Path('/private/tmp').resolve()
            try:
                metadata = expected_parent.stat()
            except OSError as exc:
                raise GitBrokerError('controlled review root is unavailable') from exc
            if (expected_parent == temporary_root or temporary_root not in expected_parent.parents or
                    expected_parent.is_symlink() or not expected_parent.is_dir() or
                    metadata.st_uid != os.getuid() or metadata.st_mode & 0o077):
                raise GitBrokerError('controlled review root must be private and under /private/tmp')
        else:
            expected_parent = self.review_copies if review else self.worker_copies
        self._inside(destination, expected_parent)
        if destination.exists() or destination.is_symlink():
            raise GitBrokerError('snapshot destination must be fresh')
        destination.mkdir(parents=True, mode=0o700)
        for relative in self._tracked(repository, revision):
            mode_type = self._git(repository, 'ls-tree', revision, '--', relative).split()[0]
            if mode_type not in ('100644', '100755'):
                raise GitBrokerError('unsupported snapshot entry mode: ' + mode_type)
            target = self._safe_relative(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = self._git_bytes(repository, 'show', revision + ':' + relative)
            with target.open('wb') as stream:
                stream.write(content)
            target.chmod(0o755 if mode_type == '100755' else 0o644)
        return destination

    def manifest(self, root, *, exclude_git=False):
        root = Path(root).resolve()
        result = {}
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise GitBrokerError('symlink in controlled workspace')
            if path.is_file():
                relative = str(path.relative_to(root))
                if exclude_git and (relative == '.git' or relative.startswith('.git/')):
                    continue
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def manifest_with_modes(self, root, *, exclude_git=False):
        """Hash regular-file content and executable semantics for boundary checks."""
        root = Path(root).resolve()
        result = {}
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise GitBrokerError('symlink in controlled workspace')
            if path.is_file():
                relative = str(path.relative_to(root))
                if exclude_git and (relative == '.git' or relative.startswith('.git/')):
                    continue
                result[relative] = {
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'mode': '100755' if path.stat().st_mode & 0o100 else '100644',
                }
        return result

    def worktree_identity(self, repository, worktree):
        repository = self._inside(repository, self.repositories)
        worktree = self._inside(worktree, self.worktrees)
        branch = branch_for_worktree(repository, worktree)
        return {
            'branch': branch,
            'revision': self.revision(repository, branch),
            'clean': self._git(repository, '-C', str(worktree), 'status', '--porcelain=v1',
                               '--untracked-files=all') == '',
            'manifest': self.manifest(worktree, exclude_git=True),
        }

    def apply_worker_changes(self, repository, worktree, worker_copy, allowed_paths, message):
        repository = self._inside(repository, self.repositories)
        worktree = self._inside(worktree, self.worktrees)
        worker_copy = self._inside(worker_copy, self.worker_copies)
        allowed = set(allowed_paths)
        tracked = set(self._tracked(repository, 'HEAD'))
        worker_manifest = self.manifest(worker_copy)
        if set(worker_manifest) != tracked:
            raise GitBrokerError('worker added, removed, or renamed a file')
        changed = []
        for relative in sorted(tracked):
            destination = self._safe_relative(worktree, relative)
            source = self._safe_relative(worker_copy, relative)
            expected_mode = self._git(repository, 'ls-tree', 'HEAD', '--', relative).split()[0]
            observed_mode = '100755' if source.stat().st_mode & 0o100 else '100644'
            if observed_mode != expected_mode:
                raise GitBrokerError('worker changed an unsupported file mode: ' + relative)
            if hashlib.sha256(destination.read_bytes()).hexdigest() != worker_manifest[relative]:
                changed.append(relative)
                if relative not in allowed:
                    raise GitBrokerError('worker changed protected path: ' + relative)
        if not changed:
            raise GitBrokerError('worker produced no changes')
        for relative in changed:
            destination = self._safe_relative(worktree, relative)
            source = self._safe_relative(worker_copy, relative)
            destination.write_bytes(source.read_bytes())
        self._git(repository, '-C', str(worktree), 'add', '--', *changed)
        self._git(repository, '-C', str(worktree), 'commit', '-m', message)
        return self.revision(repository, branch_for_worktree(repository, worktree)), changed

    def diff(self, repository, base, head):
        base = self.revision(repository, base)
        head = self.revision(repository, head)
        return self._git(repository, 'diff', '--no-ext-diff', '--binary', base, head)

    def changed_paths(self, repository, base, head):
        base = self.revision(repository, base)
        head = self.revision(repository, head)
        text = self._git(repository, 'diff', '--name-only', '--diff-filter=ACMRT', base, head)
        paths = tuple(line for line in text.splitlines() if line)
        for relative in paths:
            self._safe_relative(repository, relative)
        return paths

    def _validated_own_contribution(self, repository, contribution):
        required = {'node_id', 'worktree', 'starting_revision', 'revision',
                    'changed_paths', 'allowed_paths', 'dependencies'}
        if not isinstance(contribution, dict) or set(contribution) != required:
            raise GitBrokerError('incomplete dependency contribution')
        source = self._inside(contribution['worktree'], self.worktrees)
        start = self.revision(repository, contribution['starting_revision'])
        revision = self.revision(repository, contribution['revision'])
        try:
            self._git(repository, 'merge-base', '--is-ancestor', start, revision)
        except GitBrokerError as exc:
            raise GitBrokerError('contribution does not descend from its starting revision') from exc
        source_identity = self.worktree_identity(repository, source)
        if source_identity['revision'] != revision or not source_identity['clean']:
            raise GitBrokerError('contribution worktree does not match its declared revision')
        changed = self.changed_paths(repository, start, revision)
        declared = tuple(contribution['changed_paths'])
        if changed != declared:
            raise GitBrokerError('contribution delta does not match its declared changed paths')
        allowed = set(contribution['allowed_paths'])
        if not changed or any(path not in allowed for path in changed):
            raise GitBrokerError('contribution changed an undeclared path')
        return source, revision, changed

    def assemble_dependency_snapshot(self, repository, worktree, base_revision, contributions,
                                     message):
        """Create a deterministic assignment start from predecessor-owned deltas."""
        repository = self._inside(repository, self.repositories)
        worktree = self._inside(worktree, self.worktrees)
        base = self.revision(repository, base_revision)
        identity = self.worktree_identity(repository, worktree)
        if identity['revision'] != base or not identity['clean']:
            raise GitBrokerError('dependency snapshot worktree must be clean at the declared base')
        applied_nodes = set()
        selected = set()
        for contribution in contributions:
            node_id = contribution.get('node_id') if isinstance(contribution, dict) else None
            if not isinstance(node_id, str) or not node_id or node_id in applied_nodes:
                raise GitBrokerError('dependency snapshot contains a duplicate or invalid node')
            known_dependencies = [item for item in contribution.get('dependencies', ())
                                  if item.startswith('implement-')]
            if any(item not in applied_nodes for item in known_dependencies):
                raise GitBrokerError('dependency contributions are not in deterministic order')
            source, revision, changed = self._validated_own_contribution(repository, contribution)
            for relative in changed:
                destination = self._safe_relative(worktree, relative)
                origin = self._safe_relative(source, relative)
                destination.write_bytes(origin.read_bytes())
                selected.add(relative)
            applied_nodes.add(node_id)
        if not selected:
            return base, ()
        self._git(repository, '-C', str(worktree), 'add', '--', *sorted(selected))
        self._git(repository, '-C', str(worktree), 'commit', '-m', message)
        return self.revision(repository, branch_for_worktree(repository, worktree)), tuple(sorted(selected))

    def integrate_contributions(self, repository, worktree, base_revision, contributions, message):
        """Copy disjoint broker-validated commits into one controller-owned integration worktree."""
        repository = self._inside(repository, self.repositories)
        worktree = self._inside(worktree, self.worktrees)
        base = self.revision(repository, base_revision)
        identity = self.worktree_identity(repository, worktree)
        if identity['revision'] != base or not identity['clean']:
            raise GitBrokerError('integration worktree must be clean at the declared base')
        if contributions and all(isinstance(item, dict) and 'starting_revision' in item
                                 for item in contributions):
            return self._integrate_own_contributions(
                repository, worktree, base, contributions, message)
        selected = {}
        for contribution in contributions:
            source = self._inside(contribution['worktree'], self.worktrees)
            revision = self.revision(repository, contribution['revision'])
            source_identity = self.worktree_identity(repository, source)
            if source_identity['revision'] != revision or not source_identity['clean']:
                raise GitBrokerError('contribution worktree does not match its declared revision')
            changed = self.changed_paths(repository, base, revision)
            allowed = set(contribution['allowed_paths'])
            if not changed or any(path not in allowed for path in changed):
                raise GitBrokerError('contribution changed an undeclared path')
            for relative in changed:
                if relative in selected:
                    raise GitBrokerError('parallel contributions overlap: ' + relative)
                selected[relative] = source
        if not selected:
            raise GitBrokerError('integration has no changes')
        for relative, source in sorted(selected.items()):
            destination = self._safe_relative(worktree, relative)
            origin = self._safe_relative(source, relative)
            destination.write_bytes(origin.read_bytes())
        self._git(repository, '-C', str(worktree), 'add', '--', *sorted(selected))
        self._git(repository, '-C', str(worktree), 'commit', '-m', message)
        return self.revision(repository, branch_for_worktree(repository, worktree)), tuple(sorted(selected))

    def _integrate_own_contributions(self, repository, worktree, base, contributions, message):
        """Integrate only each assignment's own delta, allowing ordered dependent overlays."""
        graph = {item.get('node_id'): set(item.get('dependencies', ())) for item in contributions}
        if None in graph or len(graph) != len(contributions):
            raise GitBrokerError('integration contribution identities are not unique')

        def depends_on(node, ancestor, seen=None):
            seen = set() if seen is None else seen
            if node in seen:
                return False
            seen.add(node)
            direct = graph.get(node, set())
            return ancestor in direct or any(depends_on(parent, ancestor, seen)
                                             for parent in direct if parent in graph)

        applied = set()
        writers = {}
        selected = set()
        for contribution in contributions:
            node_id = contribution['node_id']
            implementation_dependencies = [item for item in contribution['dependencies']
                                           if item in graph]
            if any(item not in applied for item in implementation_dependencies):
                raise GitBrokerError('integration contributions are not in dependency order')
            source, revision, changed = self._validated_own_contribution(repository, contribution)
            for relative in changed:
                previous = writers.get(relative)
                if previous is not None and not depends_on(node_id, previous):
                    raise GitBrokerError('parallel contributions overlap: ' + relative)
                destination = self._safe_relative(worktree, relative)
                origin = self._safe_relative(source, relative)
                destination.write_bytes(origin.read_bytes())
                writers[relative] = node_id
                selected.add(relative)
            applied.add(node_id)
        if not selected:
            raise GitBrokerError('integration has no changes')
        self._git(repository, '-C', str(worktree), 'add', '--', *sorted(selected))
        self._git(repository, '-C', str(worktree), 'commit', '-m', message)
        return self.revision(repository, branch_for_worktree(repository, worktree)), tuple(sorted(selected))


def branch_for_worktree(repository, worktree):
    run = subprocess.run(['git', '-C', str(worktree), 'symbolic-ref', '--short', 'HEAD'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10)
    branch = run.stdout.decode().strip()
    if not SAFE.fullmatch(branch):
        raise GitBrokerError('invalid worktree branch')
    return branch
