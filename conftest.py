# Root conftest: registers workbench plugins. It sits at the rootdir so ``pytest_plugins`` is
# allowed, and loads after pytest.ini's ``pythonpath = src`` takes effect.
pytest_plugins = ["pytester", "qe.pytest_plugin"]
