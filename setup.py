#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages


if __name__ == "__main__":
    setup(name="migrate",
          version="0.0.2",
          description="Database Migration Assistant",
          url="https://github.com/lgastako/migrate",
          install_requires=[
              "sqlalchemy",
          ],
          packages=find_packages(),
          provides=["migrate"],
          entry_points={
              "console_scripts": [
                  "migrate = migrate:main",
              ]
          })
