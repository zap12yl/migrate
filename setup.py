#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages


if __name__ == "__main__":
    setup(name="migrator",
          version="0.0.5",
          description="Database Migration Assistant",
          author="John Evans",
          author_email="lgastako@gmail.com",
          license="MIT",
          url="https://github.com/lgastako/migrate",
          install_requires=[
              "docopt>=0.6.2",
              "sqlalchemy",
          ],
          test_requires=[
              "pytest",
              "pytest-pep8"
          ],
          packages=find_packages(),
          provides=["migrator"],
          entry_points={
              "console_scripts": [
                  "migrate = migrator:main",
              ]
          })
