test:
	sed -i 's/AsW7LnXB9UA1uec9wi9MctYTgTz7YH9snhxd16GsFaGX/4eqgQ2BwhFDdb2ujcQkz7jLXC2tU94kv4hbPkhQpEHgK/' drift-core/programs/clearing_house/src/lib.rs
	poetry run nox
	poetry run pytest -vv

lint:
	poetry run black --check --diff src tests
	poetry run flake8 src tests
	poetry run mypy src tests
