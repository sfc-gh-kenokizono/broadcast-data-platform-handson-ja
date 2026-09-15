import json
import io
import os
import socket
from importlib.metadata import version
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
os.environ['DBT_VERSION_CHECK'] = 'false'

import yaml
from dbt.cli.main import dbtRunner
from jinja2 import Environment, StrictUndefined


PROJECT = Path(__file__).resolve().parents[1]
SCOPES = ['nw01', 'nw02', 'nw03', 'nw04', 'nw05', 'common']
GRAIN = ['NETWORK_ID', 'DEVICE_ID', 'VIEW_DATE', 'GENRE']
CLEAN_COLUMNS = ['EVENT_ID', 'NETWORK_ID', 'DEVICE_ID', 'VIEW_FROM', 'VIEW_TO', 'GENRE', 'VIEW_MINUTES']
DAILY_COLUMNS = [*GRAIN, 'SESSION_COUNT', 'VIEW_MINUTES']
GENRES = ['NEWS', 'DRAMA', 'VARIETY', 'ANIME', 'SPORTS']
COMMAND_COUNTS = Counter()


def deny_network(*args, **kwargs):
    raise AssertionError('Network access is forbidden during local verification')


def invoke(arguments):
    assert arguments[0] in {'parse', 'ls'}, 'Only offline parse and list commands are allowed'
    COMMAND_COUNTS[arguments[0]] += 1
    with redirect_stdout(io.StringIO()) as output:
        result = dbtRunner().invoke(arguments)
    if not result.success:
        raise AssertionError(f'dbt local command failed: {arguments}: {result.exception}\n{output.getvalue()}')
    return result.result


def expect_failure(operation):
    try:
        operation()
    except RuntimeError:
        return
    raise AssertionError('Expected the execution scope guard to reject this selection')


def compiler_error(message):
    raise RuntimeError(message)


def verify():
    COMMAND_COUNTS.clear()
    profile = yaml.safe_load((PROJECT / 'profiles.yml').read_text())['bcast_platform']
    assert set(profile['outputs']) == set(SCOPES)
    assert not (PROJECT / 'packages.yml').exists()
    guard_source = (PROJECT / 'macros' / 'assert_execution_scope.sql').read_text()
    environment = Environment(undefined=StrictUndefined, extensions=['jinja2.ext.do'])
    project_config = yaml.safe_load((PROJECT / 'dbt_project.yml').read_text())
    assert project_config['require-dbt-version'] == ['>=1.9.0', '<2.0.0']
    assert project_config['on-run-start'] == ['{{ assert_execution_scope() }}']
    assert 'flags.WHICH' in guard_source
    schema = yaml.safe_load((PROJECT / 'models' / 'schema.yml').read_text())
    for model in schema['models']:
        for test in model.get('data_tests', []):
            if isinstance(test, dict):
                assert all('arguments' not in options for options in test.values())
        for column in model['columns']:
            for test in column.get('data_tests', []):
                if isinstance(test, dict):
                    assert all('arguments' not in options for options in test.values())
    assert len({output['warehouse'] for output in profile['outputs'].values()}) == 6
    verify_model_rendering(environment)
    summary = {}
    for scope in SCOPES:
        output = profile['outputs'][scope]
        assert output['account'] == output['user'] == ''
        assert set(output) == {
            'type', 'account', 'user', 'role', 'database', 'schema', 'warehouse', 'threads'
        }
        assert output['warehouse'] == f'BCAST_PLATFORM_{scope.upper()}_WH'
        target_path = PROJECT / 'target' / 'local_verify' / scope
        base = [
            '--project-dir', str(PROJECT), '--profiles-dir', str(PROJECT),
            '--target', scope, '--target-path', str(target_path),
            '--log-path', str(PROJECT / 'logs' / 'local_verify' / scope),
            '--no-partial-parse',
        ]
        invoke(['parse', *base])
        manifest = json.loads((target_path / 'manifest.json').read_text())
        nodes = manifest['nodes']
        models = {key: node for key, node in nodes.items() if node['resource_type'] == 'model'}
        tests = {key: node for key, node in nodes.items() if node['resource_type'] == 'test'}
        assert len(models) == 11
        assert len(manifest['sources']) == 5
        assert len(tests) == 38
        common_test = next(node for node in tests.values() if node['name'] == 'common_counts_match')
        common_parents = {
            f'model.bcast_platform_dbt.mart_device_daily_{station}' for station in SCOPES[:5]
        } | {'model.bcast_platform_dbt.viewing_daily'}
        assert set(common_test['depends_on']['nodes']) == common_parents
        assert common_test['tags'] == ['common']
        for node in models.values():
            owner = node['tags'][0]
            assert node['config']['materialized'] == 'table'
            assert node['database'] == 'BCAST_PLATFORM_HANDSON'
            assert node['schema'] == owner.upper()
            assert not node['config'].get('snowflake_warehouse')
            if node['name'].startswith('clean_viewing_'):
                assert node['alias'] == 'CLEAN_VIEWING'
                assert node['depends_on']['nodes'] == [
                    f'source.bcast_platform_dbt.raw.VIEWING_LOG_{owner.upper()}'
                ]
            elif node['name'].startswith('mart_device_daily_'):
                assert node['alias'] == 'MART_DEVICE_DAILY'
                assert node['depends_on']['nodes'] == [f'model.bcast_platform_dbt.clean_viewing_{owner}']
            else:
                assert node['alias'] == 'VIEWING_DAILY'
                assert set(node['depends_on']['nodes']) == {
                    f'model.bcast_platform_dbt.mart_device_daily_{station}' for station in SCOPES[:5]
                }
        for node in tests.values():
            assert node['config']['severity'] == 'error'
            assert not node['config']['store_failures']
            metadata = node.get('test_metadata') or {}
            if metadata.get('name') == 'unique_grain':
                assert metadata['kwargs']['columns'] == GRAIN
            if metadata.get('name') == 'not_null_columns':
                parent = models[node['depends_on']['nodes'][0]]
                expected_columns = CLEAN_COLUMNS if parent['name'].startswith('clean_') else DAILY_COLUMNS
                assert metadata['kwargs']['columns'] == expected_columns
            assert not node['config'].get('snowflake_warehouse')
        selector_rows = invoke(['ls', *base, '--selector', scope, '--output', 'json'])
        select_rows = invoke([
            'ls', *base, '--select', f'tag:{scope}', '--indirect-selection', 'cautious', '--output', 'json'
        ])
        selected = {json.loads(row)['unique_id'] for row in selector_rows}
        assert selected == {json.loads(row)['unique_id'] for row in select_rows}
        counts = Counter(nodes[key]['resource_type'] for key in selected)
        assert counts == ({'model': 1, 'test': 3} if scope == 'common' else {'model': 2, 'test': 7})
        expected_models = (
            {'model.bcast_platform_dbt.viewing_daily'} if scope == 'common' else
            {f'model.bcast_platform_dbt.{name}_{scope}' for name in ['clean_viewing', 'mart_device_daily']}
        )
        assert selected & set(models) == expected_models
        selected_tests = selected & set(tests)
        assert (common_test['unique_id'] in selected) == (scope == 'common')
        test_kinds = Counter(
            (tests[key].get('test_metadata') or {}).get('name', 'singular') for key in selected_tests
        )
        assert test_kinds == (
            {'not_null_columns': 1, 'unique_grain': 1, 'singular': 1} if scope == 'common' else
            {'not_null_columns': 2, 'unique': 1, 'accepted_values': 2, 'unique_grain': 1, 'singular': 1}
        )
        test_only = invoke(['ls', *base, '--selector', scope, '--resource-type', 'test', '--output', 'json'])
        assert {json.loads(row)['unique_id'] for row in test_only} == selected_tests
        tag_test_only = invoke([
            'ls', *base, '--select', f'tag:{scope}', '--indirect-selection', 'cautious',
            '--resource-type', 'test', '--output', 'json',
        ])
        assert {json.loads(row)['unique_id'] for row in tag_test_only} == selected_tests
        for key in selected_tests:
            metadata = tests[key].get('test_metadata') or {}
            if metadata.get('name') == 'accepted_values':
                arguments = metadata['kwargs']
                expected_values = [scope.upper()] if arguments['column_name'] == 'NETWORK_ID' else GENRES
                assert arguments['values'] == expected_values
        for key in selected:
            node = nodes[key]
            if node['resource_type'] == 'model':
                assert node['tags'] == [scope]
            if scope != 'common':
                for parent in node['depends_on']['nodes']:
                    assert parent.endswith(scope) or parent.endswith(scope.upper())
        graph = SimpleNamespace(nodes={
            key: SimpleNamespace(**{
                **node, 'depends_on': SimpleNamespace(**node['depends_on'])
            }) for key, node in nodes.items()
        })

        def render_guard(selected_ids, target_scope=scope, execute=True, omit_selection=False, command=None, **overrides):
            target_output = dict(profile['outputs'][target_scope])
            target_output.update(name=target_scope)
            target_output.update(overrides)
            context = {
                'execute': execute, 'target': SimpleNamespace(**target_output), 'graph': graph,
                'exceptions': SimpleNamespace(raise_compiler_error=compiler_error),
            }
            if not omit_selection:
                context['selected_resources'] = selected_ids
            if command is not None:
                context['flags'] = SimpleNamespace(WHICH=command)
            return environment.from_string(guard_source + '{{ assert_execution_scope() }}').render(**context)

        render_guard(selected)
        render_guard(selected_tests)
        render_guard(selected, execute=False, omit_selection=True)
        expect_failure(lambda: render_guard(selected, omit_selection=True))
        for field in ['warehouse', 'database', 'schema', 'role', 'name']:
            expect_failure(lambda field=field: render_guard(selected, **{field: 'WRONG'}))
        other_scope = 'nw01' if scope == 'common' else 'common'
        expect_failure(lambda: render_guard(selected, target_scope=other_scope))
        expect_failure(lambda: render_guard(selected_tests, target_scope=other_scope))
        expect_failure(lambda: render_guard(set(models)))
        for command in ['build', 'run', 'test']:
            render_guard(selected, command=command)
            expect_failure(lambda command=command: render_guard(set(models), command=command))
        for command in ['compile', 'parse', 'ls', 'list']:
            render_guard(set(models), command=command)
        if scope == 'common':
            expanded_rows = invoke(['ls', *base, '--select', '+tag:common', '--output', 'json'])
            expanded = {json.loads(row)['unique_id'] for row in expanded_rows}
            expect_failure(lambda: render_guard(expanded))
            indirect_rows = invoke([
                'ls', *base, '--select', 'viewing_daily', '--indirect-selection', 'cautious', '--output', 'json'
            ])
            assert common_test['unique_id'] not in {json.loads(row)['unique_id'] for row in indirect_rows}
        verify_rendered_tests(environment, manifest, selected_tests, scope)
        summary[scope] = dict(counts)
        print(f'PASS {scope}: {dict(counts)}', flush=True)
    assert COMMAND_COUNTS == {'parse': 6, 'ls': 26}
    print(json.dumps({
        'status': 'PASS', 'network': 'blocked', 'sql_execution': 'none',
        'dbt_core': version('dbt-core'), 'dbt_snowflake': version('dbt-snowflake'),
        'native_dbt_1_9': 'not executed', 'models': 11, 'data_tests': 38,
        'offline_commands': dict(COMMAND_COUNTS), 'rendered_models': 11, 'rendered_tests': 38,
        'selections': summary,
    }, indent=2))


def verify_model_rendering(environment):
    macro_source = '\n'.join(
        (PROJECT / 'macros' / filename).read_text() for filename in ['clean_viewing.sql', 'device_daily.sql']
    )
    macros = environment.from_string(macro_source).make_module()
    for scope in SCOPES[:5]:
        references = []

        def source(source_name, table):
            assert source_name == 'raw' and table == f'VIEWING_LOG_{scope.upper()}'
            references.append(table)
            return f'BCAST_PLATFORM_HANDSON.RAW.{table}'

        def ref(name):
            assert name == f'clean_viewing_{scope}'
            references.append(name)
            return f'BCAST_PLATFORM_HANDSON.{scope.upper()}.CLEAN_VIEWING'

        clean = environment.from_string(
            (PROJECT / 'models' / scope / f'clean_viewing_{scope}.sql').read_text()
        ).render(config=lambda **kwargs: '', clean_viewing=macros.clean_viewing, source=source)
        daily = environment.from_string(
            (PROJECT / 'models' / scope / f'mart_device_daily_{scope}.sql').read_text()
        ).render(config=lambda **kwargs: '', device_daily=macros.device_daily, ref=ref)
        assert references == [f'VIEWING_LOG_{scope.upper()}', f'clean_viewing_{scope}']
        assert "upper(trim(GENRE, ' \u3000'))" in clean
        for genre in GENRES:
            fullwidth = ''.join(chr(ord(character) + 0xFEE0) for character in genre)
            assert f"when '{fullwidth}' then '{genre}'" in clean
        assert 'else GENRE_KEY' in clean
        assert "datediff('millisecond', VIEW_FROM, VIEW_TO) / 60000.0" in clean
        assert not any(keyword in clean.lower() for keyword in ['where ', 'distinct ', 'qualify '])
        assert 'to_date(VIEW_FROM) as VIEW_DATE' in daily
        assert 'count(*)::integer as SESSION_COUNT' in daily
        assert 'sum(VIEW_MINUTES)::float as VIEW_MINUTES' in daily
        assert 'group by NETWORK_ID, DEVICE_ID, to_date(VIEW_FROM), GENRE' in daily
        assert 'round(' not in daily.lower()
    references = []

    def common_ref(name):
        assert name in {f'mart_device_daily_{scope}' for scope in SCOPES[:5]}
        references.append(name)
        return f'BCAST_PLATFORM_HANDSON.{name[-4:].upper()}.MART_DEVICE_DAILY'

    common = environment.from_string(
        (PROJECT / 'models' / 'common' / 'viewing_daily.sql').read_text()
    ).render(config=lambda **kwargs: '', ref=common_ref)
    assert references == [f'mart_device_daily_{scope}' for scope in SCOPES[:5]]
    assert common.count('union all') == 4
    assert common.count('select ' + ', '.join(DAILY_COLUMNS)) == 5
    assert not any(keyword in common.lower() for keyword in ['distinct ', 'group by ', 'where '])


def verify_rendered_tests(environment, manifest, selected_tests, scope):
    macro_sources = []
    for macro in manifest['macros'].values():
        if macro['name'] in {
            'test_unique_grain', 'test_not_null_columns', 'invalid_intervals',
            'default__test_unique', 'default__test_accepted_values',
        }:
            source = macro['macro_sql'].replace('{% test ', '{% macro test_').replace('{% endtest %}', '{% endmacro %}')
            macro_sources.append(source)
    assert len(macro_sources) == 5
    macros = environment.from_string('\n'.join(macro_sources)).make_module()
    for key in selected_tests:
        node = manifest['nodes'][key]
        metadata = node.get('test_metadata')
        referenced = set()

        def resolve_ref(name):
            parent_id = f'model.bcast_platform_dbt.{name}'
            referenced.add(parent_id)
            parent = manifest['nodes'][parent_id]
            if scope != 'common':
                assert parent['tags'] == [scope], 'A station test must never read another station'
            return f"{parent['database']}.{parent['schema']}.{parent['alias']}"

        if metadata:
            parent = manifest['nodes'][node['depends_on']['nodes'][0]]
            arguments = {**metadata['kwargs'], 'model': resolve_ref(parent['name'])}
            kind = metadata['name']
            prefix = 'default__test_' if kind in {'unique', 'accepted_values'} else 'test_'
            sql = getattr(macros, prefix + kind)(**arguments)
            if kind == 'not_null_columns':
                assert all(f'{column} is null' in sql for column in arguments['columns'])
                assert sql.count(' is null') == len(arguments['columns'])
            elif kind == 'unique_grain':
                assert 'group by ' + ', '.join(GRAIN) in sql
                assert 'having count(*) > 1' in sql
        else:
            sql = environment.from_string(node['raw_code']).render(
                config=lambda **kwargs: '', ref=resolve_ref, invalid_intervals=macros.invalid_intervals,
            )
            if node['name'].startswith('valid_intervals_'):
                for predicate in ['VIEW_TO <= VIEW_FROM', 'VIEW_MINUTES <= 0',
                                  'VIEW_FROM is null', 'VIEW_TO is null', 'VIEW_MINUTES is null']:
                    assert predicate in sql
            else:
                assert 'full outer join actual' in sql
                assert 'expected.ROW_COUNT != coalesce(actual.ROW_COUNT, 0)' in sql
        assert referenced == set(node['depends_on']['nodes'])
        assert '{{' not in sql and '{%' not in sql
        assert 'cross join' not in sql.lower()


if __name__ == '__main__':
    with patch.object(socket.socket, 'connect', deny_network), patch.object(
        socket, 'create_connection', deny_network
    ):
        verify()