#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages


if __name__ == "__main__":
    setup(name="migrator",
          version="0.0.3",
          description="Database Migration Assistant",
          author="John Evans",
          author_email="lgastako@gmail.com",
          license="MIT",
          url="https://github.com/lgastako/migrate",
          install_requires=[
              "sqlalchemy",
          ],
          test_requires=[
              "pytest",
              "pytest-pep8"
          ],
          packages=find_packages(),
          provides=["migrate"],
          entry_points={
              "console_scripts": [
                  "migrate = migrate:main",
              ]
          })
