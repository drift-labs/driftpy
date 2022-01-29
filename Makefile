test:
	poetry run nox
	poetry run pytest -vv

lint:
	poetry run black --check --diff src tests
	poetry run flake8 src tests
	poetry run mypy src tests
