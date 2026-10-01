"""Offline foundation and explicit Phase 2 diagnostics/smoke entry points."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .pack import catalog, check_pack, render, select
from .validation import ValidationError, read_json, validate_handoff


def _workflow_plain(events):
    """Render bounded protocol events without treating display text as authority."""
    state = {}
    task = None
    package = None
    messages = []
    for event in events:
        value = event.to_dict()
        if value.get('state') is not None:
            state = value['state']
        if value.get('task') is not None:
            task = value['task']
        if value.get('package') is not None:
            package = value['package']
        if value.get('message'):
            messages.append(value['message'])
    task = task or {}
    lines = [
        'task: ' + str(task.get('task_id', 'unknown')),
        'state: ' + str(state.get('stage', task.get('state', 'unknown'))),
        'next action: ' + str(task.get('next_action') or state.get('next_action') or 'none'),
    ]
    if state:
        if state.get('usage_known'):
            usage = '{} input, {} output'.format(state.get('input_tokens'), state.get('output_tokens'))
        else:
            usage = 'unknown'
        lines.append('usage: ' + usage)
        lines.append('assignments: {} ready, {} active, {} waiting, {} completed'.format(
            state.get('ready', 'unknown'), state.get('active', 'unknown'),
            state.get('waiting', 'unknown'), state.get('completed', 'unknown')))
        attention = state.get('attention') or ()
        if attention:
            lines.append('attention: ' + (attention if isinstance(attention, str) else
                                          ', '.join(str(item) for item in attention)))
        if state.get('blocker'):
            lines.append('blocker: ' + str(state['blocker']))
        for route in state.get('routing') or ():
            lines.append('route: {} -> {} ({})'.format(
                route.get('role', 'unknown'), route.get('provider', 'unknown'),
                route.get('reason', 'unknown')))
    if package:
        lines.extend((
            'candidate: ' + str(package.get('head_revision', 'unknown')),
            'verification: ' + str(package.get('verification_count', 'unknown')),
            'findings: ' + str(package.get('findings_count', 'unknown')),
            'approval recorded: ' + ('yes' if package.get('approval_recorded') is True else 'no'),
        ))
    lines.extend('message: ' + message for message in messages)
    return '\n'.join(lines) + '\n'


def _emit_workflow(events, output_format):
    from .integrations.openharness.protocol import event_stream

    events = tuple(events)
    if output_format == 'events':
        print(event_stream(events), end='')
    elif output_format == 'json':
        print(json.dumps({'events': [event.to_dict() for event in events]}, indent=2))
    elif output_format == 'plain':
        print(_workflow_plain(events), end='')
    else:
        from .integrations.openharness.backend import _render_with_adapted_terminal
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', suffix='.jsonl') as stream:
            stream.write(event_stream(events))
            stream.flush()
            print(_render_with_adapted_terminal(Path(stream.name)), end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description="AgentKit engineering-agent controller and evidence toolkit")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list available skills and explicit intents")
    selection = commands.add_parser("select", help="select a skill by explicit intent")
    selection.add_argument("intent")
    show = commands.add_parser("show", help="print skill and shared contract, optionally one domain")
    show.add_argument("skill")
    show.add_argument("--domain")
    validate = commands.add_parser("validate", help="validate an untrusted handoff without executing it")
    validate.add_argument("file")
    commands.add_parser("check", help="check pack references, notices and blocked examples offline")
    commands.add_parser("doctor", help="read-only version, feature, authentication and sandbox observations")
    commands.add_parser("resource-policy", help="show resource precedence and role capability profiles")
    package = commands.add_parser("package", help="export or verify a portable offline review folder")
    package_commands = package.add_subparsers(dest="package_command", required=True)
    package_export = package_commands.add_parser(
        "export", help="export an awaiting-approval workflow without executing candidate code")
    package_export.add_argument("--workflow", required=True)
    package_export.add_argument("--task-id", required=True)
    package_export.add_argument("--output", required=True, help="fresh destination directory")
    package_verify = package_commands.add_parser(
        "verify", help="verify package hashes and consistency without executing code")
    package_verify.add_argument("path")
    reuse_demo = commands.add_parser(
        "reuse-demo", help="offline deterministic OpenHarness reuse-slice demonstration")
    reuse_demo.add_argument("--output", required=True, help="fresh R0 demonstration directory")
    smoke = commands.add_parser("smoke", help="one disposable model-only CLI smoke; blocked by default")
    smoke.add_argument("engine", choices=("codex", "claude"))
    smoke.add_argument("--output", required=True, help="fresh result directory")
    smoke.add_argument("--authorize-subscription-smoke", action="store_true",
                       help="trusted operator authorization; does not establish account billing settings")
    execution = commands.add_parser("execution-check", help="one disposable owned-code CLI check; blocked by default")
    execution.add_argument("engine", choices=("codex", "claude"))
    execution.add_argument("--output", required=True, help="fresh result directory")
    execution.add_argument("--authorize-subscription-smoke", action="store_true",
                           help="trusted operator authorization; does not establish account billing settings")
    lifecycle = commands.add_parser("lifecycle-check", help="offline owned-code timeout and cancellation fixtures")
    lifecycle.add_argument("--output", required=True, help="fresh result directory")
    boundary = commands.add_parser("boundary-check", help="offline owned-code filesystem boundary canaries")
    boundary.add_argument("--output", required=True, help="fresh result directory")
    delivery = commands.add_parser("controller-demo", help="run the Phase 3 disposable delivery workflow")
    delivery.add_argument("--output", required=True, help="fresh workflow root")
    delivery.add_argument("--live", action="store_true", help="use installed subscription CLIs instead of fake engines")
    delivery.add_argument("--implementer", choices=("codex", "claude"), default="codex",
                          help="live implementer; the other provider performs review")
    delivery.add_argument("--authorize-subscription-smoke", action="store_true",
                          help="authorize one bounded disposable implementer/reviewer demonstration")
    delivery.add_argument("--resume", action="store_true",
                          help="resume the exact stage at a verified authentication checkpoint")
    delivery.add_argument("--recover-review-format", action="store_true",
                          help="offline recovery of one hash-matched provider-success fenced JSON review")
    auth_status = commands.add_parser("auth-status", help="sanitized official CLI subscription status")
    auth_status.add_argument("provider", choices=("codex", "claude"))
    auth_login = commands.add_parser("auth-login", help="official interactive subscription login; output is not captured")
    auth_login.add_argument("provider", choices=("codex", "claude"))
    auth_login.add_argument("--method", choices=("browser", "device"), default="browser")
    auth_login.add_argument("--timeout", type=float, default=600)
    auth_login.add_argument("--workflow", help="existing workflow root with an authentication checkpoint")
    auth_login.add_argument("--task-id", default="phase3-demo")
    auth_reconcile = commands.add_parser(
        "auth-reconcile", help="record process-evidence resolution for an interrupted login owner")
    auth_reconcile.add_argument("--workflow", required=True)
    auth_reconcile.add_argument("--task-id", default="phase3-demo")
    auth_reconcile.add_argument("--resolution",
                                choices=("confirmed_ended", "uncertain"), required=True)
    auth_reconcile.add_argument("--basis", required=True,
                                choices=("process_exit_confirmed", "process_termination_unconfirmed"),
                                help="sanitized process evidence; free-form terminal output is not accepted")
    project = commands.add_parser(
        "project", help="R1 read-only repository inspection, enrollment and planning")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_inspect = project_commands.add_parser(
        "inspect", help="inspect bounded Git metadata and tracked content without running project code")
    project_inspect.add_argument("path")
    project_commands.add_parser(
        "profile-example", help="print the supported R1 Python-library profile example")
    project_enroll = project_commands.add_parser(
        "enroll", help="hash-enroll a clean supported repository for read-only planning")
    project_enroll.add_argument("path")
    project_enroll.add_argument("--profile", required=True)
    project_enroll.add_argument("--state-root", required=True)
    project_show = project_commands.add_parser("show", help="show a hash-verified enrollment")
    project_show.add_argument("--state-root", required=True)
    project_show.add_argument("--project-id", required=True)
    project_plan = project_commands.add_parser(
        "plan", help="produce a non-executing plan bound to the current enrolled revision")
    project_plan.add_argument("--state-root", required=True)
    project_plan.add_argument("--project-id", required=True)
    project_plan.add_argument("--request", required=True)
    task = commands.add_parser("task", help="Phase 4 disposable task intake and orchestration")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    task_commands.add_parser("fixtures", help="list supported controller-created disposable targets")
    task_propose = task_commands.add_parser(
        "propose", help="inspect request-driven planning without creating a workflow")
    task_propose.add_argument("--project", required=True)
    task_propose.add_argument("--request", required=True)
    task_submit = task_commands.add_parser("submit", help="normalize a request and propose a bounded plan")
    task_submit.add_argument("--root", required=True, help="fresh workflow directory")
    task_submit.add_argument("--task-id", required=True)
    target = task_submit.add_mutually_exclusive_group(required=True)
    target.add_argument("--project", help="controller-created disposable project scenario")
    target.add_argument("--fixture", help="backward-compatible alias for --project")
    task_submit.add_argument("--request", required=True)
    task_submit.add_argument("--risk", choices=("routine", "material"))
    task_submit.add_argument("--max-calls", type=int)
    task_submit.add_argument("--max-elapsed-seconds", type=float)
    task_submit.add_argument("--max-concurrency", type=int, choices=(1, 2))
    task_submit.add_argument("--max-provider-calls", type=int)
    task_submit.add_argument("--max-planning-calls", type=int, default=0)
    task_submit.add_argument("--max-repairs", type=int, choices=(0, 1, 2), default=2)
    task_submit.add_argument("--max-escalations", type=int, choices=(0, 1, 2))
    task_submit.add_argument("--implementation-timeout", type=float, default=60)
    task_submit.add_argument("--review-timeout", type=float, default=60)
    task_submit.add_argument("--verification-timeout", type=float, default=10)
    task_submit.add_argument("--routing-config", help="validated portable model registry JSON")
    task_submit.add_argument("--implementer-provider", choices=("codex", "claude"), default="codex",
                             help="account-default provider for implementation and bounded repair")
    task_submit.add_argument("--reviewer-provider", choices=("codex", "claude"), default="claude",
                             help="account-default provider for independent review")
    for name, help_text in (
            ("plan", "show the validated contract and proposed graph"),
            ("status", "show stage, assignments, routing, budget, blockers, and attention"),
            ("cancel", "request cancellation and prevent subsequent launches"),
            ("package", "read the final local approval package")):
        command = task_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True)
        command.add_argument("--task-id", required=True)
    for name, help_text in (("start", "start or continue the proposed bounded workflow"),
                            ("resume", "resume an authentication checkpoint after verified login")):
        command = task_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True)
        command.add_argument("--task-id", required=True)
        command.add_argument("--live", action="store_true")
        command.add_argument("--authorize-subscription-smoke", action="store_true")
    product = commands.add_parser(
        "product", help="provider-planned controller-created static web product")
    product_commands = product.add_subparsers(dest="product_command", required=True)
    product_submit = product_commands.add_parser(
        "submit", help="run one bounded provider planning call and record a validated proposal")
    product_submit.add_argument("--root", required=True, help="fresh workflow directory")
    product_submit.add_argument("--task-id", required=True)
    product_submit.add_argument("--brief-file", required=True)
    product_submit.add_argument("--acceptance-file", required=True)
    product_submit.add_argument("--mechanics-test", required=True)
    product_submit.add_argument("--routing-config")
    product_submit.add_argument("--max-calls", type=int)
    product_submit.add_argument("--max-provider-calls", type=int)
    product_submit.add_argument("--max-concurrency", type=int, choices=(1, 2))
    product_submit.add_argument("--max-repairs", type=int, choices=(0, 1, 2))
    product_submit.add_argument("--max-retries", type=int, choices=(0, 1, 2))
    product_submit.add_argument("--max-escalations", type=int, choices=(0, 1, 2))
    product_submit.add_argument("--max-elapsed-seconds", type=float)
    product_submit.add_argument("--planning-timeout", type=float)
    product_submit.add_argument("--implementation-timeout", type=float)
    product_submit.add_argument("--review-timeout", type=float)
    product_submit.add_argument("--verification-timeout", type=float)
    product_submit.add_argument("--live", action="store_true")
    product_submit.add_argument("--authorize-subscription-smoke", action="store_true")
    for name, help_text in (
            ("plan", "show the provider proposal and validated graph"),
            ("status", "show product stage, resources, blockers and attention"),
            ("cancel", "request bounded workflow cancellation"),
            ("package", "read the revision-bound local approval package"),
            ("preview-serve", "serve the reviewed candidate until Ctrl+C and confirm cleanup")):
        command = product_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True)
        command.add_argument("--task-id", required=True)
    for name, help_text in (("start", "execute the validated product plan"),
                            ("resume", "resume a verified product authentication checkpoint")):
        command = product_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True)
        command.add_argument("--task-id", required=True)
        command.add_argument("--live", action="store_true")
        command.add_argument("--authorize-subscription-smoke", action="store_true")
    browser_record = product_commands.add_parser(
        "browser-record", help="validate exact-revision controller-owned browser evidence")
    browser_record.add_argument("--root", required=True)
    browser_record.add_argument("--task-id", required=True)
    browser_record.add_argument("--evidence", required=True)
    workflow = commands.add_parser(
        "workflow", help="operate an existing Phase 4 disposable workflow through the terminal protocol")
    workflow_commands = workflow.add_subparsers(dest="workflow_command", required=True)
    for name, help_text in (
            ("status", "read current controller status"),
            ("start", "start or continue the bounded workflow"),
            ("resume", "resume a verified authentication checkpoint"),
            ("cancel", "request cancellation and prevent subsequent launches"),
            ("package", "read the local approval-package summary")):
        command = workflow_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True, help="existing Phase 4 workflow root")
        command.add_argument("--task-id", required=True)
        command.add_argument("--format", choices=("plain", "json", "events", "terminal"),
                             default="plain")
        if name in ("start", "resume"):
            command.add_argument("--live", action="store_true")
            command.add_argument("--authorize-subscription-smoke", action="store_true",
                                 help="authorize bounded live provider execution for this invocation")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(json.dumps(catalog(), indent=2))
        elif args.command == "select":
            print(json.dumps(select(args.intent), indent=2))
        elif args.command == "show":
            print(render(args.skill, args.domain))
        elif args.command == "validate":
            result = validate_handoff(read_json(args.file))
            print(json.dumps({"valid": True, "kind": result["kind"],
                              "status": result["status"], "authority": "none",
                              "note": "Structure and consistency only; claims are not authenticated."}))
        elif args.command == "doctor":
            from .doctor import doctor
            print(json.dumps(doctor(), indent=2))
        elif args.command == "resource-policy":
            from .resource_policy import policy_document
            print(json.dumps(policy_document(), indent=2))
        elif args.command == "package":
            from .portable_package import export_package, verify_package
            result = (export_package(args.workflow, args.task_id, args.output)
                      if args.package_command == 'export' else verify_package(args.path))
            print(json.dumps(result, indent=2))
            return 0
        elif args.command == "smoke":
            from .smoke import smoke_test
            result = smoke_test(args.engine, args.output, args.authorize_subscription_smoke)
            print(json.dumps(result, indent=2))
            return 0 if result['acceptance']['passed'] else 1
        elif args.command == "execution-check":
            from .execution_check import run_execution_check
            result = run_execution_check(args.engine, args.output, args.authorize_subscription_smoke)
            print(json.dumps(result, indent=2))
            return 0 if result['acceptance']['passed'] else 1
        elif args.command == "lifecycle-check":
            from .execution_check import lifecycle_check
            result = lifecycle_check(args.output)
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        elif args.command == "boundary-check":
            from .execution_check import standalone_boundary_check
            result = standalone_boundary_check(args.output)
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        elif args.command == "controller-demo":
            from .delivery import (DeliveryWorkflow, LiveImplementer, LiveReviewer, run_demo)
            if args.resume and args.recover_review_format:
                raise ValueError('choose either authentication resume or review-format recovery')
            if args.recover_review_format:
                if not args.live or not args.authorize_subscription_smoke:
                    raise ValueError('review-format recovery requires the original live authorization context')
                workflow = DeliveryWorkflow.open(args.output, LiveImplementer(args.implementer),
                                                 LiveReviewer('claude' if args.implementer == 'codex' else 'codex'),
                                                 live_authorized=True)
                result = workflow.recover_review_format()
            else:
                result = run_demo(args.output, live=args.live, authorized=args.authorize_subscription_smoke,
                                  implementer_engine=args.implementer, resume=args.resume)
            print(json.dumps({'task': result['task'], 'approval_package': result['approval_package'],
                              'root': result['root']}, indent=2))
            return 0 if result['task']['state'] in ('awaiting_pr_approval', 'authentication_required') else 1
        elif args.command == "auth-status":
            from .auth import probe_authentication
            print(json.dumps(probe_authentication(args.provider).to_dict(), indent=2))
        elif args.command == "auth-login":
            from .auth import guided_login, safe_login_reason
            from .controller import ControllerStore
            if args.provider == 'claude' and args.method != 'browser':
                raise ValueError('Claude Code supports browser login with manual code handoff, not device mode')
            store = None
            claim = None
            if args.workflow:
                root = Path(args.workflow).resolve()
                store = ControllerStore(root / 'controller')
                if sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty():
                    claim = store.claim_authentication_login(args.task_id, args.provider,
                                                              authority=store.authority)
                    if not claim['claimed'] and claim['status'] == 'in_progress':
                        print(json.dumps({
                            'provider': args.provider,
                            'status': 'login_ownership_requires_reconciliation',
                            'machine': 'this host',
                            'session_id': claim['session_id'],
                            'next_action': ('Confirm whether the prior official login process is still running. '
                                            'If it ended, use auth-reconcile --resolution confirmed_ended; '
                                            'if termination cannot be established, use --resolution uncertain.')
                        }, indent=2))
                        return 1
                    if not claim['claimed'] and claim['status'] == 'succeeded':
                        print(json.dumps({'provider': args.provider, 'status': 'already_authenticated',
                                          'machine': 'this host'}, indent=2))
                        return 0
            try:
                result = guided_login(args.provider, args.method, timeout_seconds=args.timeout)
            except KeyboardInterrupt:
                if store is not None and claim is not None and claim['claimed']:
                    store.reconcile_authentication_login(
                        claim['session_id'], 'uncertain',
                        'controller_interrupted',
                        authority=store.authority)
                print(json.dumps({'provider': args.provider, 'status': 'cancelled',
                                  'termination': 'uncertain'}, indent=2))
                return 130
            except Exception:
                if store is not None and claim is not None and claim['claimed']:
                    store.reconcile_authentication_login(
                        claim['session_id'], 'uncertain',
                        'launcher_exception',
                        authority=store.authority)
                raise
            if store is not None and claim is not None and claim['claimed']:
                if result.termination == 'uncertain':
                    store.reconcile_authentication_login(
                        claim['session_id'], 'uncertain',
                        'process_termination_unconfirmed',
                        authority=store.authority)
                else:
                    outcome = 'succeeded' if result.status in ('succeeded', 'already_authenticated') else (
                        'timed_out' if result.status == 'timed_out' else
                        'cancelled' if result.status == 'cancelled' else 'failed')
                    store.finish_authentication_login(
                        claim['session_id'], outcome, auth_mode=result.authentication.mode,
                        reason=safe_login_reason(result), owner_nonce=claim['owner_nonce'],
                        authority=store.authority)
            print(json.dumps(result.to_dict(), indent=2))
            return 0 if result.status in ('succeeded', 'already_authenticated') else 1
        elif args.command == "reuse-demo":
            from .integrations.openharness import run_deterministic_demo
            result = run_deterministic_demo(args.output)
            print(json.dumps(result, indent=2))
            return 0 if result['metadata']['final_state'] == 'awaiting_pr_approval' else 1
        elif args.command == "auth-reconcile":
            from .controller import ControllerStore
            root = Path(args.workflow).resolve()
            store = ControllerStore(root / 'controller')
            checkpoint = store.authentication_checkpoint(args.task_id)
            if not checkpoint:
                raise ValueError('task has no active authentication checkpoint')
            status = store.reconcile_authentication_login(
                checkpoint['login_session_id'], args.resolution, args.basis,
                authority=store.authority)
            print(json.dumps({'task_id': args.task_id, 'session_id': checkpoint['login_session_id'],
                              'status': status}, indent=2))
            return 0
        elif args.command == "project":
            from .projects import (ProjectRegistry, example_python_profile, inspect_project,
                                   validate_project_profile)
            if args.project_command == "inspect":
                print(json.dumps(inspect_project(args.path), indent=2))
            elif args.project_command == "profile-example":
                print(json.dumps(example_python_profile(), indent=2))
            elif args.project_command == "enroll":
                profile = validate_project_profile(read_json(args.profile))
                print(json.dumps(ProjectRegistry(args.state_root).enroll(args.path, profile), indent=2))
            elif args.project_command == "show":
                print(json.dumps(ProjectRegistry(args.state_root).load(args.project_id), indent=2))
            else:
                print(json.dumps(ProjectRegistry(args.state_root).plan(
                    args.project_id, args.request), indent=2))
            return 0
        elif args.command == "task":
            from .orchestration import Phase4Workflow, phase4_fixture_catalog
            if args.task_command == 'fixtures':
                print(json.dumps({'execution_profile': 'trusted-disposable-macos',
                                  'fixtures': phase4_fixture_catalog()}, indent=2))
                return 0
            if args.task_command == 'propose':
                from .phase4_fixtures import get_fixture
                from .planning import bounded_inventory, propose
                fixture = get_fixture(args.project)
                print(json.dumps({'inventory': bounded_inventory(fixture),
                                  'proposal': propose(args.request, fixture)}, indent=2))
                return 0
            if args.task_command == 'submit':
                from .phase4_contracts import ModelRegistry
                registry = (ModelRegistry.from_dict(read_json(args.routing_config))
                            if args.routing_config else
                            ModelRegistry.account_defaults(args.implementer_provider,
                                                           args.reviewer_provider))
                workflow = Phase4Workflow.submit(
                    args.root, args.task_id, args.request, args.project or args.fixture, risk=args.risk,
                    max_calls=args.max_calls, max_elapsed_seconds=args.max_elapsed_seconds,
                    max_concurrency=args.max_concurrency, registry=registry,
                    max_provider_calls=args.max_provider_calls,
                    max_planning_calls=args.max_planning_calls, max_repairs=args.max_repairs,
                    max_escalations=args.max_escalations,
                    implementation_timeout_seconds=args.implementation_timeout,
                    review_timeout_seconds=args.review_timeout,
                    verification_timeout_seconds=args.verification_timeout)
                print(json.dumps({'contract': json.loads((workflow.root / 'contract.json').read_text()),
                                  'plan': json.loads((workflow.root / 'plan.json').read_text()),
                                  'status': workflow.status(args.task_id)}, indent=2))
                return 0
            live = getattr(args, 'live', False)
            authorized = getattr(args, 'authorize_subscription_smoke', False)
            if live and not authorized:
                raise ValueError('live Phase 4 execution requires explicit subscription-smoke authorization')
            workflow = Phase4Workflow(args.root, live=live, authorized=authorized)
            if args.task_command == 'plan':
                print(json.dumps({'contract': json.loads((workflow.root / 'contract.json').read_text()),
                                  'plan': workflow.state.plan(args.task_id)['plan']}, indent=2))
            elif args.task_command == 'status':
                print(json.dumps(workflow.status(args.task_id), indent=2))
            elif args.task_command == 'start':
                print(json.dumps(workflow.start(args.task_id), indent=2))
            elif args.task_command == 'resume':
                print(json.dumps(workflow.resume(args.task_id), indent=2))
            elif args.task_command == 'cancel':
                print(json.dumps(workflow.cancel(args.task_id), indent=2))
            else:
                package = workflow.result(args.task_id)['approval_package']
                if package is None:
                    raise ValueError('local approval package is not available')
                print(json.dumps(package, indent=2))
            return 0
        elif args.command == "product":
            from .product import ProductWorkflow
            if args.product_command == 'submit':
                if not args.live or not args.authorize_subscription_smoke:
                    raise ValueError(
                        'product planning uses a provider and requires explicit live subscription authorization')
                from .phase4_contracts import ModelRegistry
                registry = (ModelRegistry.from_dict(read_json(args.routing_config))
                            if args.routing_config else ModelRegistry.account_defaults())
                acceptance = read_json(args.acceptance_file)
                workflow = ProductWorkflow.submit_product(
                    args.root, args.task_id, Path(args.brief_file).read_text(), acceptance,
                    Path(args.mechanics_test).read_text(), registry=registry, live=True,
                    authorized=True, max_calls=args.max_calls,
                    max_provider_calls=args.max_provider_calls,
                    max_concurrency=args.max_concurrency, max_repairs=args.max_repairs,
                    max_retries=args.max_retries,
                    max_escalations=args.max_escalations,
                    max_elapsed_seconds=args.max_elapsed_seconds,
                    planning_timeout_seconds=args.planning_timeout,
                    implementation_timeout_seconds=args.implementation_timeout,
                    review_timeout_seconds=args.review_timeout,
                    verification_timeout_seconds=args.verification_timeout)
                result = workflow.status(args.task_id)
                if (workflow.root / 'plan.json').is_file():
                    result = {'contract': read_json(workflow.root / 'contract.json'),
                              'plan': read_json(workflow.root / 'plan.json'), 'status': result}
                print(json.dumps(result, indent=2))
                return 0 if result.get('state', result.get('status', {}).get('state')) != 'blocked' else 1
            live = getattr(args, 'live', False)
            authorized = getattr(args, 'authorize_subscription_smoke', False)
            if live and not authorized:
                raise ValueError('live product execution requires explicit subscription authorization')
            workflow = ProductWorkflow(args.root, live=live, authorized=authorized)
            if args.product_command == 'plan':
                print(json.dumps({'request': read_json(workflow.root / 'product-request.json'),
                                  'contract': read_json(workflow.root / 'contract.json'),
                                  'plan': read_json(workflow.root / 'plan.json')}, indent=2))
            elif args.product_command == 'status':
                print(json.dumps(workflow.status(args.task_id), indent=2))
            elif args.product_command == 'start':
                print(json.dumps(workflow.start(args.task_id), indent=2))
            elif args.product_command == 'resume':
                print(json.dumps(workflow.resume(args.task_id), indent=2))
            elif args.product_command == 'cancel':
                print(json.dumps(workflow.cancel(args.task_id), indent=2))
            elif args.product_command == 'preview-serve':
                workflow.serve_preview(
                    args.task_id,
                    ready_callback=lambda session: print(json.dumps(session), flush=True))
                print(json.dumps({'status': 'stopped', 'cleanup_confirmed': True}, indent=2))
            elif args.product_command == 'browser-record':
                print(json.dumps(workflow.record_browser_evidence(
                    args.task_id, read_json(args.evidence)), indent=2))
            else:
                package = workflow.result(args.task_id)['approval_package']
                if package is None:
                    raise ValueError('local product approval package is not available')
                print(json.dumps(package, indent=2))
            return 0
        elif args.command == "workflow":
            from .integrations.openharness.protocol import FrontendRequest
            from .terminal_workflow import TerminalWorkflow

            live = getattr(args, 'live', False)
            authorized = getattr(args, 'authorize_subscription_smoke', False)
            if live and not authorized:
                raise ValueError('live workflow execution requires explicit subscription authorization')
            if authorized and not live:
                raise ValueError('subscription authorization is valid only with --live')
            request_type = 'package_summary' if args.workflow_command == 'package' else args.workflow_command
            backend = TerminalWorkflow(args.root, args.task_id, live=live, authorized=authorized)
            events = backend.handle(FrontendRequest(request_type, args.task_id))
            _emit_workflow(events, args.format)
            return 0
        else:
            print(json.dumps(check_pack(), indent=2))
        return 0
    except (ValidationError, OSError, KeyError, RuntimeError, ValueError) as exc:
        print("agentkit: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
