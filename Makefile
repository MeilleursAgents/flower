PACKAGE_ROOT = 'flower'
VENV_PREFIX = $(shell echo $(PACKAGE_ROOT) | tr [a-z] [A-Z])
VENV_NAME = py36-$(PACKAGE_ROOT)


PIP = $(WORKON_HOME)/$(VENV_NAME)/bin/pip3
PYTHON = $(WORKON_HOME)/$(VENV_NAME)/bin/python3
VIRTUALENV = $(PYENV_ROOT)/versions/3.6.0/bin/virtualenv


LINT_OPTION = --max-line-length 180 --ignore _ --import-order-style=edited --application-import-names=listing_models,tests


init: init-venv update-venv
	$(PIP) install -Ur requirements.txt


init-dev: init
	$(PIP) install -Ur requirements-dev.txt


init-venv:
	test -d $(WORKON_HOME)/$(VENV_NAME) || $(VIRTUALENV) $(WORKON_HOME)/$(VENV_NAME)


update-venv:
	$(PIP) install -Ur requirements.txt


deinit:
	rm -r $(WORKON_HOME)/$(VENV_NAME)


lint:
	$(WORKON_HOME)/$(VENV_NAME)/bin/flake8 $(LINT_OPTION) .


test: lint
	$(WORKON_HOME)/$(VENV_NAME)/bin/py.test tests


test-debug: lint
	$(WORKON_HOME)/$(VENV_NAME)/bin/py.test --ipdb tests


assets:
	true || true


coverage: lint
	$(WORKON_HOME)/$(VENV_NAME)/bin/py.test --cov . --cov-report term-missing --cov-report xml --junitxml=junit-coverage.xml --cov-config .coveragerc tests


clean:
	true || true


package:
	python setup.py sdist

release:
	python setup.py sdist upload -r ma
