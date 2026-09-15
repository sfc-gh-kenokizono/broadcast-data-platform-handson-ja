{% macro assert_execution_scope() %}
    {% set command = flags.WHICH if flags is defined and flags.WHICH is defined else 'build' %}
    {% if execute and command not in ['compile', 'parse', 'ls', 'list'] %}
        {% set scopes = ['nw01', 'nw02', 'nw03', 'nw04', 'nw05', 'common'] %}
        {% if target.name not in scopes %}
            {{ exceptions.raise_compiler_error('Use an explicit station or common target.') }}
        {% endif %}
        {% if selected_resources is not defined %}
            {{ exceptions.raise_compiler_error('Execution scope is unavailable; stop and check the dbt runtime.') }}
        {% endif %}
        {% set expected_warehouse = 'BCAST_PLATFORM_' ~ (target.name | upper) ~ '_WH' %}
        {% if target.warehouse != expected_warehouse
              or target.database != 'BCAST_PLATFORM_HANDSON'
              or target.schema != (target.name | upper)
              or target.role != 'BCAST_PLATFORM_ENGINEER_ROLE' %}
            {{ exceptions.raise_compiler_error('Target does not match the contract: ' ~ target.name) }}
        {% endif %}
        {% for resource_id in selected_resources %}
            {% set resource = graph.nodes.get(resource_id) %}
            {% if resource and resource.resource_type in ['model', 'test'] %}
                {% set owners = [] %}
                {% for scope in scopes if scope in resource.tags %}
                    {% do owners.append(scope) %}
                {% endfor %}
                {% if resource.resource_type == 'test' and not owners %}
                    {% for parent_id in resource.depends_on.nodes %}
                        {% set parent = graph.nodes.get(parent_id) %}
                        {% if parent %}
                            {% for scope in scopes if scope in parent.tags and scope not in owners %}
                                {% do owners.append(scope) %}
                            {% endfor %}
                        {% endif %}
                    {% endfor %}
                {% endif %}
                {% if owners != [target.name] %}
                    {{ exceptions.raise_compiler_error(
                        'Selection/target mismatch: ' ~ resource.name ~ ' belongs to ' ~
                        (owners | join(',')) ~ '; target is ' ~ target.name ~
                        '. Use --selector ' ~ target.name ~ ' without graph expansion.'
                    ) }}
                {% endif %}
            {% endif %}
        {% endfor %}
    {% endif %}
{% endmacro %}