all:
	@cat Makefile

freeze:
	pip freeze > requirements.txt

install-dev:
	pip install -e .

register:
	python setup.py register

test:
	py.test

upload:
	python setup.py sdist upload

f: freeze
i: install-dev
r: register
t: test
u: upload
