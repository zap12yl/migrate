all:
	@cat Makefile

freeze:
	pip freeze > requirements.txt

register:
	python setup.py register

test:
	py.test

upload:
	python setup.py sdist upload

f: freeze
r: register
t: test
u: upload
