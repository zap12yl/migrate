all:
	@cat Makefile

freeze:
	pip freeze > requirements.txt

test:
	py.test

upload:
	python setup.py sdist upload

t: test
u: upload
