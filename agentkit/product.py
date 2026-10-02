"""Bounded provider-planned delivery for controller-created static web products."""

from dataclasses import asdict
import hashlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from .adapters import execute
from .controller import ControllerError, UsageRecord
from .delivery import EngineOutcome, LiveImplementer
from .doctor import clean_environment, native_sandbox_capability, verification_profile
from .orchestration import (Phase4Workflow, _manifest, build_contract, build_plan)
from .phase4_contracts import ModelRegistry
from .paths import resource_root
from .phase4_fixtures import FixtureSpec, FixtureSubtask
from .planning import bounded_inventory
from .process import run_process
from .runtime_contracts import ExecutionRequest
from .resource_policy import (output_exhaustion_recovery, resolve_product_task_budget,
                              resolve_role_resources)
from .web_acceptance import (WebAcceptanceError, create_preview_snapshot,
                             validate_browser_report)


PRODUCT_SCHEMA_VERSION = 1
WEB_EDITABLE_PATHS = ('README.md', 'game.js', 'index.html', 'styles.css')
WEB_CORE_PATHS = frozenset(('game.js', 'index.html', 'styles.css'))
WEB_SEED_FILES = {
    'README.md': '# Controller-created static web product\n',
    'game.js': '',
    'index.html': ('<!doctype html>\n<meta charset="utf-8">\n'
                   '<title>Controller-created web product</title>\n'
                   '<main id="app"></main>\n<script src="game.js"></script>\n'),
    'styles.css': '',
    'package.json': json.dumps({
        'name': 'controller-created-static-product', 'private': True, 'version': '0.0.0',
        'scripts': {'build': 'node --check game.js'}}, indent=2) + '\n',
}
PRODUCT_PROJECT_POLICY = {
    'stack': 'vanilla-static',
    'dependency_install': 'none',
    'build': 'node-check',
    'preview': 'loopback-python-http',
    'browser_verification': 'required',
}
class ProductPlanningError(ControllerError):
    pass


def _bounded(value, name, maximum=32768):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > maximum:
        raise ValueError(name + ' must be a nonempty bounded string')
    return value.strip()


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def static_web_inventory():
    seed = FixtureSpec('product-static-web-seed', 'Blank controller-created static web project.',
                       'substantial', 'material', 'frontend', WEB_SEED_FILES,
                       {path: WEB_SEED_FILES[path] for path in WEB_EDITABLE_PATHS},
                       '/* controller acceptance supplied separately */\n', (), ())
    return bounded_inventory(seed)


def planning_context(toolkit_root):
    root = Path(toolkit_root).resolve()
    # Planning receives only the role-relevant product skills. Acceptance design
    # is intentionally held for the independent acceptance-preparation role.
    selected = ('skills/task-contract/SKILL.md', 'skills/product-shaping/SKILL.md',
                'skills/interface-design/SKILL.md', 'skills/interaction-design/SKILL.md',
                'skills/visual-design/SKILL.md', 'domains/frontend.md')
    items = []
    total = 0
    for relative in selected:
        target = (root / relative).resolve()
        if root not in target.parents or target.is_symlink() or not target.is_file():
            raise ProductPlanningError('planning context path is unavailable')
        raw = target.read_bytes()
        total += len(raw)
        if total > 16384:
            raise ProductPlanningError('planning context exceeds its bounded allocation')
        items.append({'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(),
                      'content': raw.decode('utf-8')})
    return {'schema_version': 1, 'role': 'tech_lead', 'bytes': total, 'items': items}


def planner_prompt(brief, acceptance, inventory, limits, context):
    schema = {
        'project': PRODUCT_PROJECT_POLICY,
        'proposal': {
            'objective': '<brief objective>',
            'requirements': [{'source': 'user', 'text': '<exact brief>'}],
            'assumptions': ['<explicit bounded assumption>'],
            'acceptance': acceptance,
            'assignments': [{
                'id': 'implement-<name>', 'objective': '<bounded deliverable>',
                'allowed_paths': ['<path from inventory>'],
                'dependencies': [], 'interfaces': ['<interface contract>'],
            }],
            'interfaces': [{'assignment': 'implement-<name>', 'contract': '<contract>'}],
            'dependencies': [],
            'integration_strategy': '<controller-owned strategy>',
            'verification_requirements': ['controller-owned mechanics checks'],
            'review_requirements': ['independent review of exact revision'],
            'roles': ['chief_of_staff', 'tech_lead', 'implementer', 'verifier', 'reviewer'],
            'model_profiles': {'implementer': 'controller-route', 'repair': 'controller-route',
                               'reviewer': 'controller-independent-route'},
            'resource_allocations': {'implementation_calls': 1,
                                     'verification_calls': 1, 'review_calls': 1,
                                     'maximum_concurrent_implementers': 1},
            'inventory_sha256': inventory['sha256'],
            'planner': {'kind': 'provider-tech-lead', 'model_call': True},
        },
    }
    return (
        'Plan one bounded static web product. Return only one JSON object matching the supplied shape. '
        'The controller will reject extra paths, operations, cycles, missing criteria and budget excess. '
        'Use one cohesive implementation assignment unless a real independently writable boundary makes '
        'two assignments materially useful. Do not provide source code, a finished solution, shell commands, '
        'credentials, publication steps, external services or authority changes. The only editable files are '
        + ', '.join(WEB_EDITABLE_PATHS) + '. No dependency installation is available.\n'
        'PRODUCT_BRIEF:\n' + brief + '\n'
        'CONTROLLER_ACCEPTANCE_JSON:\n' + json.dumps(acceptance, sort_keys=True) + '\n'
        'WORKSPACE_INVENTORY_JSON:\n' + json.dumps(inventory, sort_keys=True) + '\n'
        'CAPABILITIES_AND_LIMITS_JSON:\n' + json.dumps(limits, sort_keys=True) + '\n'
        'VERIFIED_PLANNING_CONTEXT_JSON:\n' + json.dumps(context, sort_keys=True) + '\n'
        'REQUIRED_OUTPUT_SHAPE_JSON:\n' + json.dumps(schema, sort_keys=True)
    )


def validate_product_document(document, brief, acceptance, inventory, *, max_subtasks,
                              max_concurrency):
    if not isinstance(document, dict) or set(document) != {'project', 'proposal'}:
        raise ProductPlanningError('product planner returned an unsupported document shape')
    if document['project'] != PRODUCT_PROJECT_POLICY:
        raise ProductPlanningError('product planner requested unsupported project operations')
    proposal = document['proposal']
    required = {'objective', 'requirements', 'assumptions', 'acceptance', 'assignments',
                'interfaces', 'dependencies', 'integration_strategy',
                'verification_requirements', 'review_requirements', 'roles', 'model_profiles',
                'resource_allocations', 'inventory_sha256', 'planner'}
    if not isinstance(proposal, dict) or set(proposal) != required:
        raise ProductPlanningError('product proposal has an unsupported shape')
    if proposal['inventory_sha256'] != inventory['sha256']:
        raise ProductPlanningError('product proposal targets a stale inventory')
    if proposal['acceptance'] != acceptance:
        raise ProductPlanningError('product proposal changed controller-owned acceptance')
    if proposal['requirements'] != [{'source': 'user', 'text': brief}]:
        raise ProductPlanningError('product proposal changed the user requirement')
    if (not isinstance(proposal['objective'], str) or not proposal['objective'].strip() or
            not isinstance(proposal['assumptions'], list) or not proposal['assumptions'] or
            any(not isinstance(item, str) or not item.strip() for item in proposal['assumptions'])):
        raise ProductPlanningError('product proposal lacks a bounded objective or assumptions')
    planner = proposal['planner']
    if planner != {'kind': 'provider-tech-lead', 'model_call': True}:
        raise ProductPlanningError('product proposal has an unsupported planner identity')
    assignments = proposal['assignments']
    if not isinstance(assignments, list) or not 1 <= len(assignments) <= max_subtasks:
        raise ProductPlanningError('product proposal exceeds the assignment bound')
    identifiers = set()
    paths_by_id = {}
    graph = {}
    for assignment in assignments:
        if (not isinstance(assignment, dict) or
                set(assignment) != {'id', 'objective', 'allowed_paths', 'dependencies', 'interfaces'}):
            raise ProductPlanningError('product assignment has an unsupported shape')
        node_id = assignment['id']
        if (not isinstance(node_id, str) or not node_id.startswith('implement-') or
                not node_id.replace('-', '').isalnum() or node_id in identifiers):
            raise ProductPlanningError('product assignment identity is invalid or duplicated')
        _bounded(assignment['objective'], 'assignment objective', 2048)
        if (not isinstance(assignment['allowed_paths'], list) or
                not assignment['allowed_paths'] or
                any(path not in WEB_EDITABLE_PATHS for path in assignment['allowed_paths'])):
            raise ProductPlanningError('product assignment expands path authority')
        if (not isinstance(assignment['dependencies'], list) or
                not isinstance(assignment['interfaces'], list) or
                any(not isinstance(value, str) or not value.strip()
                    for value in assignment['dependencies'] + assignment['interfaces'])):
            raise ProductPlanningError('product assignment dependencies or interfaces are invalid')
        identifiers.add(node_id)
        paths_by_id[node_id] = set(assignment['allowed_paths'])
        graph[node_id] = set(assignment['dependencies'])
    if set().union(*paths_by_id.values()) < WEB_CORE_PATHS:
        raise ProductPlanningError('product proposal omits a required static-web deliverable')
    expected_interfaces = {
        (assignment['id'], interface)
        for assignment in assignments for interface in assignment['interfaces']
    }
    actual_interfaces = {
        (item.get('assignment'), item.get('contract'))
        for item in proposal['interfaces'] if isinstance(item, dict) and
        set(item) == {'assignment', 'contract'} and
        isinstance(item.get('contract'), str) and item.get('contract').strip()
    }
    if (len(actual_interfaces) != len(proposal['interfaces']) or
            actual_interfaces != expected_interfaces):
        raise ProductPlanningError('product interface summary does not match assignments')
    if any(not deps <= identifiers for deps in graph.values()):
        raise ProductPlanningError('product proposal references an unknown dependency')
    expected_edges = {(source, target) for target, deps in graph.items() for source in deps}
    actual_edges = {(item.get('source'), item.get('target'))
                    for item in proposal['dependencies'] if isinstance(item, dict) and
                    set(item) == {'source', 'target'}}
    if len(actual_edges) != len(proposal['dependencies']) or actual_edges != expected_edges:
        raise ProductPlanningError('product dependency summary does not match assignments')
    for left in identifiers:
        for right in identifiers:
            if left < right and not graph[left] and not graph[right] and paths_by_id[left] & paths_by_id[right]:
                raise ProductPlanningError('independent product assignments overlap')
    pending = {node: set(deps) for node, deps in graph.items()}
    ready = sorted(node for node, deps in pending.items() if not deps)
    visited = []
    while ready:
        node = ready.pop(0)
        visited.append(node)
        for target in sorted(pending):
            if node in pending[target]:
                pending[target].remove(node)
                if not pending[target] and target not in visited and target not in ready:
                    ready.append(target)
                    ready.sort()
    if len(visited) != len(identifiers):
        raise ProductPlanningError('product proposal contains a dependency cycle')
    allocations = proposal['resource_allocations']
    if (not isinstance(allocations, dict) or
            allocations != {'implementation_calls': len(assignments),
                            'verification_calls': 1, 'review_calls': 1,
                            'maximum_concurrent_implementers': min(max_concurrency, len(assignments))}):
        raise ProductPlanningError('product proposal resource allocation is infeasible')
    if not all(isinstance(value, list) and value for value in
               (proposal['verification_requirements'], proposal['review_requirements'],
                proposal['roles'], proposal['interfaces'])):
        raise ProductPlanningError('product proposal lacks verification, review, roles or interfaces')
    return proposal


def _dynamic_fixture(proposal, acceptance_test):
    subtasks = []
    for assignment in proposal['assignments']:
        subtasks.append(FixtureSubtask(
            assignment['id'].removeprefix('implement-'), assignment['objective'],
            tuple(assignment['allowed_paths']), (),
            tuple(dep.removeprefix('implement-') for dep in assignment['dependencies']),
            tuple(assignment['interfaces']), (), ''))
    return FixtureSpec(
        'product-static-web', 'Provider-planned controller-created static web product.',
        'substantial', 'material', 'frontend', dict(WEB_SEED_FILES),
        {path: WEB_SEED_FILES[path] for path in WEB_EDITABLE_PATHS},
        acceptance_test, tuple(proposal['acceptance']), tuple(subtasks))


def _fixture_document(fixture):
    return {
        'schema_version': PRODUCT_SCHEMA_VERSION,
        'fixture_id': fixture.fixture_id, 'description': fixture.description,
        'difficulty': fixture.difficulty, 'risk': fixture.risk, 'domain': fixture.domain,
        'files': fixture.files, 'final_files': fixture.final_files,
        'acceptance_test': fixture.acceptance_test,
        'acceptance': list(fixture.acceptance),
        'subtasks': [asdict(item) for item in fixture.subtasks],
    }


def _fixture_from_document(value):
    if not isinstance(value, dict) or value.get('schema_version') != PRODUCT_SCHEMA_VERSION:
        raise ProductPlanningError('unsupported product fixture document')
    return FixtureSpec(
        value['fixture_id'], value['description'], value['difficulty'], value['risk'], value['domain'],
        value['files'], value['final_files'], value['acceptance_test'], tuple(value['acceptance']),
        tuple(FixtureSubtask(**{**item,
                               'allowed_paths': tuple(item['allowed_paths']),
                               'request_terms': tuple(item['request_terms']),
                               'dependencies': tuple(item['dependencies']),
                               'interfaces': tuple(item['interfaces']),
                               'acceptance': tuple(item['acceptance'])})
              for item in value['subtasks']))


def _usage(result):
    value = result.usage
    return UsageRecord(value.input_tokens, value.output_tokens, value.cached_input_tokens,
                       value.cache_creation_tokens, value.reasoning_tokens,
                       value.estimated_cost_usd, value.billed_cost_usd, value.source)


class LiveProductPlanner:
    def __init__(self, provider, model=None, effort=None, *, timeout_seconds=None,
                 max_output_bytes=None, max_generated_output_tokens=None):
        self.provider = provider
        self.model = model
        self.effort = effort
        self.resources = resolve_role_resources(
            'planning', task_timeout_seconds=timeout_seconds,
            task_capture_bytes=max_output_bytes,
            provider_output_tokens=max_generated_output_tokens)
        self.timeout_seconds = self.resources['timeout_seconds']['value']
        self.max_output_bytes = self.resources['max_capture_bytes']['value']
        self.max_generated_output_tokens = self.resources['generated_output_tokens']['value']

    def run(self, prompt, output, policy, cancel_event=None):
        with tempfile.TemporaryDirectory(prefix='agentkit-product-plan-') as tmp:
            request = ExecutionRequest(
                self.provider, 'phase4-product-planner', prompt, str(Path(tmp).resolve()),
                timeout_seconds=self.timeout_seconds, max_output_bytes=self.max_output_bytes,
                model=self.model, effort=self.effort, mode='model-only',
                capability_profile='structured-planning',
                max_generated_output_tokens=self.max_generated_output_tokens,
                resource_resolution=self.resources)
            result = execute(request, output, policy=policy, cancel_event=cancel_event)
        return EngineOutcome(
            result.status, result.elapsed_seconds, _usage(result),
            {'error_class': result.error_class, 'proposal_document': result.structured_output,
             'artifacts': result.artifacts, 'limitations': result.limitations,
             'resource_resolution': self.resources,
             'requested_configuration': {'model': self.model, 'effort': self.effort},
             'provider_reported_configuration': {
                 'model': result.model, 'effort': result.provider_details.get('effort')},
             'authentication_failure': result.provider_details.get('authentication_failure')})

    def without_output_override(self, *, remaining_calls, remaining_seconds):
        recovered = output_exhaustion_recovery(
            self.resources, remaining_calls=remaining_calls,
            remaining_seconds=remaining_seconds)
        if recovered is None:
            return None
        planner = LiveProductPlanner(
            self.provider, self.model, self.effort,
            timeout_seconds=min(self.timeout_seconds, remaining_seconds),
            max_output_bytes=self.max_output_bytes)
        planner.resources['generated_output_tokens'] = recovered['generated_output_tokens']
        planner.max_generated_output_tokens = None
        return planner


class StaticProductPlanner:
    """Deterministic fixture planner used only by offline tests."""

    def __init__(self, document, provider='claude', model=None, effort=None):
        self.document = document
        self.provider = provider
        self.model = model
        self.effort = effort
        self.calls = 0

    def run(self, prompt, output, policy, cancel_event=None):
        self.calls += 1
        Path(output).mkdir(mode=0o700)
        (Path(output) / 'request.json').write_text(json.dumps({
            'provider': self.provider, 'model': self.model, 'effort': self.effort,
            'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'prompt_bytes': len(prompt.encode()), 'simulated': True}, indent=2) + '\n')
        return EngineOutcome(
            'succeeded', .01, UsageRecord(source='fake'),
            {'proposal_document': self.document, 'simulated': True,
             'requested_configuration': {'model': self.model, 'effort': self.effort},
             'provider_reported_configuration': {'model': None, 'effort': None}})


VERIFY_RUNNER = r'''import subprocess, sys
node, acceptance = sys.argv[1:]
commands = ([node, '--check', 'game.js'], [node, acceptance])
for command in commands:
    run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, timeout=10, check=False)
    print('$ ' + ' '.join(command))
    print(run.stdout)
    if run.returncode:
        raise SystemExit(run.returncode)
'''


class WebProductVerifier:
    engine = 'local'
    model = 'node-static-product-acceptance-v1'

    def __init__(self, broker, acceptance_test, node_executable, controller_root, approval_root,
                 evidence_root, *, constrained, timeout_seconds=20,
                 max_output_bytes=1048576, capability_check=native_sandbox_capability,
                 process_runner=run_process):
        self.broker = broker
        self.acceptance_test = acceptance_test
        self.node_executable = str(Path(node_executable).resolve())
        self.controller_root = Path(controller_root).resolve()
        self.approval_root = Path(approval_root).resolve()
        self.evidence_root = Path(evidence_root).resolve()
        self.constrained = constrained
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.capability_check = capability_check
        self.process_runner = process_runner

    def run(self, repository, worktree, head, attempt, cancel_event=None):
        capability = self.capability_check() if self.constrained else None
        if capability is not None and capability.state != 'verified':
            return EngineOutcome('blocked', 0, UsageRecord(source='unavailable'),
                                 {'error_class': 'sandbox_unavailable',
                                  'output': capability.evidence, 'candidate_unchanged': None})
        before = self.broker.worktree_identity(repository, worktree)
        if before['revision'] != head or not before['clean']:
            return EngineOutcome('failed', 0, UsageRecord(source='local-command'),
                                 {'error_class': 'candidate_identity',
                                  'output': 'candidate is dirty or at another revision',
                                  'candidate_unchanged': False})
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix='agentkit-web-verify-', dir='/private/tmp') as tmp:
            root = Path(tmp).resolve()
            workspace, runtime, fake_home = root / 'candidate', root / 'runtime', root / 'empty-home'
            for path in (workspace, runtime, fake_home):
                path.mkdir(mode=0o700)
            for relative in before['manifest']:
                target = workspace / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((Path(worktree) / relative).read_bytes())
            acceptance = workspace / 'controller-acceptance.mjs'
            runner = workspace / 'controller-verify.py'
            acceptance.write_text(self.acceptance_test)
            runner.write_text(VERIFY_RUNNER)
            node_copy = runtime / 'node'
            shutil.copy2(self.node_executable, node_copy)
            node_copy.chmod(0o700)
            controlled_before = _manifest(workspace)
            environment = clean_environment()
            executable_path = ':'.join((str(runtime), '/usr/bin', '/bin'))
            environment.update(HOME=str(fake_home), TMPDIR=str(runtime),
                               PATH=executable_path,
                               PYTHONDONTWRITEBYTECODE='1')
            argv = [sys.executable, '-B', str(runner), str(node_copy), str(acceptance)]
            sandbox_evidence = None
            if self.constrained:
                denied = tuple(str(path) for path in (
                    self.controller_root, self.approval_root, self.evidence_root,
                    Path(repository).resolve(), Path(worktree).resolve(), Path.home().resolve()))
                argv = ['/usr/bin/sandbox-exec', '-p', verification_profile(runtime, denied)] + argv
                sandbox_evidence = capability.evidence
            outcome = self.process_runner(
                argv, cwd=str(workspace), env=environment, timeout=self.timeout_seconds,
                max_bytes=self.max_output_bytes, cancel_event=cancel_event)
            controlled_after = _manifest(workspace)
        after = self.broker.worktree_identity(repository, worktree)
        unchanged = (before == after and before['revision'] == head and before['clean'] and
                     controlled_before == controlled_after)
        status = 'succeeded' if outcome.exit_code == 0 and unchanged else 'failed'
        return EngineOutcome(
            status, time.monotonic() - started, UsageRecord(source='local-command'),
            {'exit_code': outcome.exit_code, 'stop_reason': outcome.stop_reason,
             'output': (outcome.stdout + outcome.stderr).decode('utf-8', 'replace'),
             'candidate_unchanged': unchanged, 'sandbox': sandbox_evidence,
             'checks': ['node --check game.js', 'controller-owned mechanics acceptance']})


class ProductWorkflow(Phase4Workflow):
    @classmethod
    def submit_product(cls, root, task_id, brief, acceptance, mechanics_test, *,
                       registry=None, planner=None, live=False, authorized=False,
                       max_calls=None, max_provider_calls=None, max_concurrency=None,
                       max_repairs=None, max_retries=None, max_escalations=None,
                       max_elapsed_seconds=None,
                       planning_timeout_seconds=None, implementation_timeout_seconds=None,
                       review_timeout_seconds=None, verification_timeout_seconds=None,
                       max_output_bytes=None):
        root = Path(root).resolve()
        if root.exists() or root.is_symlink():
            raise ControllerError('product workflow root must be fresh')
        brief = _bounded(brief, 'product brief')
        mechanics_test = _bounded(mechanics_test, 'controller mechanics test')
        if (not isinstance(acceptance, list) or not acceptance or len(acceptance) > 32 or
                any(not isinstance(item, dict) or set(item) != {'id', 'expected'} or
                    not isinstance(item['id'], str) or not item['id'] or
                    not isinstance(item['expected'], str) or not item['expected']
                    for item in acceptance) or
                len({item['id'] for item in acceptance}) != len(acceptance)):
            raise ValueError('product acceptance must contain unique bounded id/expected objects')
        task_budget = resolve_product_task_budget(
            max_calls=max_calls, max_provider_calls=max_provider_calls,
            max_concurrency=max_concurrency, max_repairs=max_repairs,
            max_retries=max_retries, max_escalations=max_escalations,
            max_elapsed_seconds=max_elapsed_seconds)
        budget_values = {name: item['value'] for name, item in task_budget.items()}
        max_calls = budget_values['max_calls']
        max_provider_calls = budget_values['max_provider_calls']
        max_concurrency = budget_values['max_concurrency']
        max_repairs = budget_values['max_repairs']
        max_retries = budget_values['max_retries']
        max_escalations = budget_values['max_escalations']
        max_elapsed_seconds = budget_values['max_elapsed_seconds']
        stage_resources = {
            'planning': resolve_role_resources(
                'planning', task_timeout_seconds=planning_timeout_seconds,
                task_capture_bytes=max_output_bytes),
            'implementation': resolve_role_resources(
                'web-implementation', task_timeout_seconds=implementation_timeout_seconds,
                task_capture_bytes=max_output_bytes),
            'review': resolve_role_resources(
                'review', task_timeout_seconds=review_timeout_seconds,
                task_capture_bytes=max_output_bytes),
            'verification': resolve_role_resources(
                'verification', task_timeout_seconds=verification_timeout_seconds,
                task_capture_bytes=max_output_bytes),
        }
        planning_timeout_seconds = stage_resources['planning']['timeout_seconds']['value']
        implementation_timeout_seconds = stage_resources['implementation']['timeout_seconds']['value']
        review_timeout_seconds = stage_resources['review']['timeout_seconds']['value']
        verification_timeout_seconds = stage_resources['verification']['timeout_seconds']['value']
        max_output_bytes = stage_resources['planning']['max_capture_bytes']['value']
        max_timeout_seconds = max(planning_timeout_seconds, implementation_timeout_seconds,
                                  review_timeout_seconds, verification_timeout_seconds)
        root.mkdir(parents=True, mode=0o700)
        for name in ('evidence', 'approval'):
            (root / name).mkdir(mode=0o700)
        self = cls(root, live=live, authorized=authorized)
        registry = registry or ModelRegistry.account_defaults()
        planner_route = registry.route('product-plan', 'tech_lead', 'model-only',
                                       difficulty='substantial', risk='material')
        implementation_route = registry.route('product-implementation', 'implementer', 'owned-code',
                                              difficulty='substantial', risk='material')
        review_route = registry.route(
            'product-review', 'reviewer', 'model-only',
            exclude_providers=(implementation_route.provider,),
            difficulty='substantial', risk='material')
        self.store.create_task(
            task_id, brief, implementer=(implementation_route.provider, implementation_route.model),
            reviewer=(review_route.provider, review_route.model), max_repairs=max_repairs,
            max_calls=max_calls, max_elapsed_seconds=max_elapsed_seconds,
            max_concurrency=max_concurrency, max_timeout_seconds=max_timeout_seconds,
            verification_reserve=1, review_reserve=1,
            max_provider_calls=max_provider_calls,
            max_planning_calls=1 + max_retries)
        inventory = static_web_inventory()
        context = planning_context(resource_root())
        limits = {
            'provider_invocations_total': max_provider_calls,
            'planning_calls_max': 1 + max_retries, 'implementation_assignments_max': 2,
            'concurrent_workers_max': max_concurrency, 'repair_calls_max': max_repairs,
            'stage_timeout_seconds': {
                'planning': planning_timeout_seconds,
                'implementation': implementation_timeout_seconds,
                'review': review_timeout_seconds},
            'overall_seconds': max_elapsed_seconds,
            'dependency_install': 'unsupported; use the dependency-free static stack',
            'publication': 'unsupported',
        }
        prompt = planner_prompt(brief, acceptance, inventory, limits, context)
        planner = planner or (LiveProductPlanner(
            planner_route.provider, planner_route.model, planner_route.effort,
            timeout_seconds=planning_timeout_seconds,
            max_output_bytes=max_output_bytes) if live else None)
        if planner is None:
            raise ProductPlanningError('offline product submission requires a deterministic planner fixture')
        self._write_json('product-request.json', {
            'schema_version': 1, 'brief': brief, 'acceptance': acceptance,
            'inventory': inventory, 'limits': limits,
            'resource_policy': {'task_budget': task_budget,
                                'stage_allocations': stage_resources},
            'planning_route': planner_route.to_dict(),
            'planning_context': [{k: item[k] for k in ('path', 'sha256')}
                                 for item in context['items']],
        })
        self._write_json('registry.json', registry.to_dict())
        outcome, execution_id = self._run_engine(
            task_id, 'planning', planner_route.provider, planner_route.model,
            planning_timeout_seconds,
            lambda: planner.run(prompt, self.evidence_root / 'planning-0', self.policy,
                                cancel_event=self._cancellation(task_id)),
            effort=planner_route.effort)
        attempts = [{'execution_id': execution_id, 'status': outcome.status,
                     'details': outcome.details, 'usage': asdict(outcome.usage)}]
        if (outcome.status == 'failed' and
                outcome.details.get('error_class') == 'output_limit' and
                max_retries > 0 and hasattr(planner, 'without_output_override')):
            recovered = planner.without_output_override(
                remaining_calls=max_retries,
                remaining_seconds=max_elapsed_seconds - outcome.elapsed_seconds)
            if recovered is not None:
                planner = recovered
                outcome, execution_id = self._run_engine(
                    task_id, 'planning', planner_route.provider, planner_route.model,
                    planner.timeout_seconds,
                    lambda: planner.run(
                        prompt, self.evidence_root / 'planning-1', self.policy,
                        cancel_event=self._cancellation(task_id)),
                    effort=planner_route.effort)
                attempts.append({'execution_id': execution_id, 'status': outcome.status,
                                 'details': outcome.details,
                                 'usage': asdict(outcome.usage)})
        self._write_json('planning-result.json', {
            'execution_id': execution_id, 'status': outcome.status,
            'details': outcome.details, 'usage': asdict(outcome.usage),
            'attempts': attempts})
        if outcome.status != 'succeeded':
            self._transition(task_id, 'received', 'blocked', 'planning-blocked',
                             'inspect bounded product planning failure')
            self._write_product_preplan_status(task_id)
            return self
        try:
            raw_document = outcome.details.get('proposal_document')
            raw_proposal = validate_product_document(
                raw_document, brief, acceptance, inventory,
                max_subtasks=2, max_concurrency=max_concurrency)
            implementation_count = len(raw_proposal['assignments'])
            mandatory_calls = 1 + implementation_count + 1 + 1
            provider_calls = 1 + implementation_count + 1
            allocated_time = (planning_timeout_seconds +
                              implementation_count * implementation_timeout_seconds +
                              verification_timeout_seconds + review_timeout_seconds)
            if (mandatory_calls > max_calls or provider_calls > max_provider_calls or
                    allocated_time > max_elapsed_seconds):
                raise ProductPlanningError(
                    'validated product plan cannot fit mandatory planning, implementation, '
                    'verification and review reserves')
            fixture = _dynamic_fixture(raw_proposal, mechanics_test)
            proposal = json.loads(json.dumps(raw_proposal))
            proposal['planner'] = {
                **proposal['planner'],
                'provider': planner_route.provider, 'profile_id': planner_route.profile_id,
                'requested_model': planner_route.model, 'requested_effort': planner_route.effort,
                'routing_reason': planner_route.reason,
                'source_inventory_sha256': inventory['sha256'],
            }
            proposal['inventory_sha256'] = bounded_inventory(fixture)['sha256']
            contract = build_contract(
                task_id, brief, fixture, risk='material', max_calls=max_calls,
                max_elapsed_seconds=max_elapsed_seconds, max_concurrency=max_concurrency,
                max_provider_calls=max_provider_calls,
                max_planning_calls=1 + max_retries,
                max_repairs=max_repairs, max_retries=max_retries,
                max_escalations=max_escalations,
                implementation_timeout_seconds=implementation_timeout_seconds,
                review_timeout_seconds=review_timeout_seconds,
                verification_timeout_seconds=verification_timeout_seconds,
                max_timeout_seconds=max_timeout_seconds,
                max_output_bytes_per_call=max_output_bytes, proposal=proposal)
            plan = build_plan(
                contract, fixture, registry, resource_root(), proposal,
                planner_accounted=True)
        except Exception as exc:
            self._write_json('planner-rejection.json', {
                'error': type(exc).__name__, 'reason': str(exc),
                'raw_document_sha256': hashlib.sha256(
                    json.dumps(outcome.details.get('proposal_document'), sort_keys=True).encode()).hexdigest(),
            })
            self._transition(task_id, 'received', 'blocked', 'planner-output-rejected',
                             'inspect rejected untrusted product plan')
            self._write_product_preplan_status(task_id)
            return self
        node = shutil.which('node')
        if not node:
            self._transition(task_id, 'received', 'blocked', 'node-unavailable',
                             'install no dependencies; provide an already-installed Node.js runtime')
            self._write_product_preplan_status(task_id)
            return self
        self._write_json('product-spec.json', {
            'schema_version': 1, 'fixture': _fixture_document(fixture),
            'project_policy': PRODUCT_PROJECT_POLICY,
            'node': {'executable': str(Path(node).resolve()),
                     'sha256': hashlib.sha256(Path(node).resolve().read_bytes()).hexdigest(),
                     'version': subprocess.run([node, '--version'], text=True,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               timeout=5, check=True).stdout.strip()},
            'launch': {'build': 'node --check game.js',
                       'preview': 'python3 -m http.server PORT --bind 127.0.0.1'},
            'raw_planner_document_sha256': hashlib.sha256(
                json.dumps(outcome.details['proposal_document'], sort_keys=True).encode()).hexdigest(),
        })
        spec_bytes = (self.root / 'product-spec.json').read_bytes()
        spec_digest = self.store.put_artifact(spec_bytes)
        self.store.append_event(
            task_id, task_id + '-product-spec-bound', 'product_spec_bound',
            {'artifact_sha256': spec_digest, 'bytes': len(spec_bytes)},
            authority=self.store.authority)
        self.state.record_intake(contract, fixture.fixture_id, authority=self.store.authority)
        self.store.set_contract(task_id, contract.controller_contract(), authority=self.store.authority)
        self.store.transition(task_id, 'received', 'contracted',
                              task_id + '-product-contracted',
                              next_action='review provider-proposed product plan',
                              authority=self.store.authority)
        self.state.record_plan(plan, authority=self.store.authority)
        self._write_json('contract.json', contract.to_dict())
        self._write_json('plan.json', plan.to_dict())
        self._write_status(task_id)
        return self

    def _write_product_preplan_status(self, task_id):
        task = self.store.task(task_id)
        snapshot = self.store.snapshot(task_id)
        self._write_json('status.json', {
            'task_id': task_id, 'state': task['state'], 'stage': 'planning',
            'next_action': task['next_action'], 'executions': snapshot['executions'],
            'approval_package': None})

    def _fixture(self, task_id):
        target = self.root / 'product-spec.json'
        if not target.is_file():
            return super()._fixture(task_id)
        bindings = [event for event in self.store.snapshot(task_id)['events']
                    if event['event_type'] == 'product_spec_bound']
        if len(bindings) != 1:
            raise ProductPlanningError('product specification has no unique controller binding')
        binding = json.loads(bindings[0]['payload_json'])
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if (digest != binding.get('artifact_sha256') or
                binding.get('bytes') != len(target.read_bytes()) or
                not self.store.artifact_intact(digest)):
            raise ProductPlanningError('product specification changed after planning')
        return _fixture_from_document(json.loads(target.read_text())['fixture'])

    def _requires_browser_verification(self, task_id):
        return (self.root / 'product-spec.json').is_file()

    def _adapter(self, provider, fixture, model=None, effort=None):
        if self.specialist_factory:
            return self.specialist_factory(provider, fixture)
        contract = json.loads((self.root / 'contract.json').read_text())
        return (LiveImplementer(
            provider, model, effort,
            timeout_seconds=contract['implementation_timeout_seconds'],
            max_output_bytes=contract['max_output_bytes_per_call'],
            capability_profile='web-product-implementation',
            resource_role='web-implementation') if self.live else
                super()._adapter(provider, fixture, model, effort))

    def _verifier(self, task_id, fixture):
        if self.verifier_factory:
            return self.verifier_factory(self.broker, fixture)
        contract = json.loads((self.root / 'contract.json').read_text())
        self._fixture(task_id)  # Recheck the immutable product specification immediately before use.
        spec = json.loads((self.root / 'product-spec.json').read_text())
        node = Path(spec['node']['executable']).resolve()
        if (not node.is_file() or hashlib.sha256(node.read_bytes()).hexdigest() != spec['node']['sha256']):
            raise ControllerError('recorded Node.js runtime changed after product planning')
        return WebProductVerifier(
            self.broker, fixture.acceptance_test, node, self.controller_root,
            self.approval_root, self.evidence_root, constrained=self.live,
            timeout_seconds=contract['verification_timeout_seconds'],
            max_output_bytes=contract['max_output_bytes_per_call'])

    def status(self, task_id):
        if not (self.root / 'plan.json').is_file():
            task = self.store.task(task_id)
            snapshot = self.store.snapshot(task_id)
            return {'task_id': task_id, 'state': task['state'], 'stage': 'planning',
                    'next_action': task['next_action'], 'executions': snapshot['executions'],
                    'approval_package': None}
        return super().status(task_id)

    def _package(self, task_id, repository):
        package = super()._package(task_id, repository)
        package['summary'] = self.store.task(task_id)['objective']
        package['proposed_pr'] = {
            'title': 'Build controller-planned static web product',
            'body': ('Implements the validated product brief and records deterministic mechanics, '
                     'browser interaction and independent review evidence.')}
        package['local_launch'] = json.loads((self.root / 'product-spec.json').read_text())['launch']
        package['limitations'].extend([
            'The generated browser product is trusted disposable code, not a hostile-input boundary.',
            'Browser credential isolation and universal browser egress control are not established.',
            'External dependency installation is unsupported; this profile is dependency-free.',
        ])
        return package

    def serve_preview(self, task_id, *, stop_event=None, ready_callback=None):
        """Serve the exact reviewed candidate in the foreground and clean up in this owner."""
        task = self.store.task(task_id)
        if task['state'] != 'review_complete' or not self._requires_browser_verification(task_id):
            raise ControllerError('preview requires a reviewed product awaiting browser acceptance')
        identity = self._candidate_identity(task_id)
        if identity['revision'] != task['head_revision'] or not identity['clean']:
            raise ControllerError('preview candidate identity is stale or dirty')
        session_path = self.evidence_root / 'preview-session.json'
        if session_path.exists():
            previous = json.loads(session_path.read_text())
            if previous.get('status') == 'running':
                raise ControllerError('existing preview ownership requires explicit reconciliation')
        manifest = self.broker.manifest(Path(task['worktree']), exclude_git=True)
        snapshot_root = self._fresh(self.evidence_root, 'preview-snapshot')
        try:
            preview = create_preview_snapshot(
                task['worktree'], snapshot_root, manifest, task['head_revision'])
        except WebAcceptanceError as exc:
            raise ControllerError('preview snapshot rejected: ' + str(exc)) from exc
        handler = partial(SimpleHTTPRequestHandler, directory=preview['snapshot_root'])
        try:
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        except OSError as exc:
            raise ControllerError('loopback preview is unavailable on this host: ' +
                                  type(exc).__name__) from exc
        server.timeout = .1
        port = server.server_address[1]
        session = {
            'schema_version': 1, 'status': 'running', 'pid': os.getpid(),
            'process_group': os.getpgrp(), 'argv': ['agentkit', 'product', 'preview-serve'],
            'port': port, 'url': 'http://127.0.0.1:' + str(port) + '/',
            'candidate_revision': task['head_revision'], 'candidate_identity': identity,
            'session_id': preview['session_id'],
            'snapshot_sha256': preview['snapshot_sha256'],
            'manifest_sha256': preview['manifest_sha256'],
            'snapshot_root': preview['snapshot_root'],
            'started_monotonic': time.monotonic(),
            'containment_limit': ('Foreground controller-owned loopback server only; browser egress '
                                  'and remote browser effects are not contained.'),
        }
        session_path.write_text(json.dumps(session, indent=2, sort_keys=True) + '\n')
        if ready_callback:
            ready_callback(dict(session))
        try:
            while stop_event is None or not stop_event.is_set():
                server.handle_request()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            session.update(status='stopped', cleanup_confirmed=True,
                           stopped_monotonic=time.monotonic())
            session_path.write_text(json.dumps(session, indent=2, sort_keys=True) + '\n')
        return session

    def _implementation_authors(self, task_id):
        authors = []
        for item in self.store.snapshot(task_id)['executions']:
            if item['role'] in ('implementer', 'implementation', 'repair') and item['status'] == 'succeeded':
                label = item['engine']
                if label not in authors:
                    authors.append(label)
        if not authors:
            raise ControllerError('browser evidence has no successful implementation author')
        return authors

    def record_browser_evidence(self, task_id, evidence):
        task = self.store.task(task_id)
        if task['state'] != 'review_complete':
            raise ControllerError('browser evidence requires the reviewed candidate')
        actual = self._candidate_identity(task_id)
        if isinstance(evidence, dict) and 'session_id' in evidence:
            session_path = self.evidence_root / 'preview-session.json'
            if not session_path.is_file():
                raise ControllerError('browser evidence requires a recorded owned preview session')
            session = json.loads(session_path.read_text())
            receipt = {
                'schema_version': 1,
                'candidate_revision': session.get('candidate_revision'),
                'session_id': session.get('session_id'),
                'snapshot_sha256': session.get('snapshot_sha256'),
                'status': session.get('status'),
                'cleanup_confirmed': session.get('cleanup_confirmed'),
            }
            try:
                normalized = validate_browser_report(
                    evidence, acceptance=task['contract']['acceptance'],
                    candidate_revision=task['head_revision'], preview_receipt=receipt,
                    evidence_root=self.evidence_root,
                    implementation_authors=self._implementation_authors(task_id))
            except WebAcceptanceError as exc:
                raise ControllerError('browser evidence rejected: ' + str(exc)) from exc
            if actual['revision'] != task['head_revision'] or not actual['clean']:
                raise ControllerError('browser evidence is bound to another candidate')
            artifact = self.store.put_artifact(json.dumps(normalized, sort_keys=True))
            evidence_id = 'product-browser-' + str(task['repair_count'])
            self.store.add_evidence(
                task_id, evidence_id, task['head_revision'], 'browser-check',
                normalized['status'], artifact, normalized, authority=self.store.authority)
            self._write_json(
                'evidence/browser-evidence-' + str(task['repair_count']) + '.json', normalized)
            if normalized['status'] == 'failed':
                failed = [item for item in normalized['checks'] if item['status'] == 'failed']
                if normalized['visual_judgment']['status'] == 'failed':
                    failed.append({'visual_judgment': normalized['visual_judgment']})
                signature = hashlib.sha256(json.dumps(failed, sort_keys=True).encode()).hexdigest()
                decision = self.store.record_failure(
                    task_id, signature, json.dumps(failed), authority=self.store.authority)
                if decision == 'repair_allowed':
                    self._transition(task_id, 'review_complete', 'repairing', 'repair-browser',
                                     'repair concrete browser acceptance failure')
                self._write_status(task_id)
                return self.result(task_id)
            return self._drive(task_id)
        if (not isinstance(evidence, dict) or
                set(evidence) != {'schema_version', 'candidate_revision', 'browser', 'checks',
                                 'screenshots', 'visual_judgment', 'preview_cleanup'} or
                evidence.get('schema_version') != 1 or
                evidence.get('candidate_revision') != task['head_revision'] or
                actual['revision'] != task['head_revision'] or not actual['clean']):
            raise ControllerError('browser evidence is malformed or bound to another candidate')
        checks = evidence['checks']
        required_check_ids = {item['id'] for item in task['contract']['acceptance']}
        if (not isinstance(checks, list) or len(checks) != len(required_check_ids) or
                {item.get('id') for item in checks if isinstance(item, dict)} != required_check_ids or
                any(set(item) != {'id', 'status', 'observation'} or
                    item['status'] not in ('passed', 'failed') or
                    not isinstance(item['observation'], str) or not item['observation'].strip()
                    for item in checks)):
            raise ControllerError('browser evidence does not cover every required interaction')
        if (not isinstance(evidence['browser'], dict) or
                not isinstance(evidence['browser'].get('name'), str) or
                not evidence['browser']['name'] or
                evidence['visual_judgment'] != 'user_review_required' or
                evidence['preview_cleanup'] is not True):
            raise ControllerError('browser identity, visual judgment and preview cleanup are required')
        session_path = self.evidence_root / 'preview-session.json'
        if not session_path.is_file():
            raise ControllerError('browser evidence requires a recorded owned preview session')
        session = json.loads(session_path.read_text())
        if (session.get('candidate_revision') != task['head_revision'] or
                session.get('status') != 'stopped' or session.get('cleanup_confirmed') is not True):
            raise ControllerError('browser evidence requires confirmed cleanup of the exact preview')
        screenshots = evidence['screenshots']
        if not isinstance(screenshots, list):
            raise ControllerError('browser screenshots must be a list')
        for item in screenshots:
            if not isinstance(item, dict) or set(item) != {'path', 'sha256', 'viewport'}:
                raise ControllerError('invalid browser screenshot record')
            target = (self.evidence_root / item['path']).resolve()
            if (self.evidence_root not in target.parents or not target.is_file() or
                    _sha256(target) != item['sha256']):
                raise ControllerError('browser screenshot is absent, escaping, or changed')
        passed = all(item['status'] == 'passed' for item in checks)
        artifact = self.store.put_artifact(json.dumps(evidence, sort_keys=True))
        evidence_id = 'product-browser-' + str(task['repair_count'])
        self.store.add_evidence(task_id, evidence_id, task['head_revision'], 'browser-check',
                                'passed' if passed else 'failed', artifact, evidence,
                                authority=self.store.authority)
        self._write_json('evidence/browser-evidence-' + str(task['repair_count']) + '.json', evidence)
        if not passed:
            failed = [item for item in checks if item['status'] == 'failed']
            signature = hashlib.sha256(json.dumps(failed, sort_keys=True).encode()).hexdigest()
            decision = self.store.record_failure(task_id, signature, json.dumps(failed),
                                                 authority=self.store.authority)
            if decision == 'repair_allowed':
                self._transition(task_id, 'review_complete', 'repairing', 'repair-browser',
                                 'repair concrete browser acceptance failure')
            self._write_status(task_id)
            return self.result(task_id)
        return self._drive(task_id)
