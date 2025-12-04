#!/bin/bash
set -e  

echo "Running tests:"
pytest -v -s -x tests/ci/*.py
# pytest -v -s tests/math/*.py

exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo "Tests failed with exit code $exit_code"
    exit $exit_code
fi

echo "All tests passed successfully"