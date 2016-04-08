#!/usr/bin/env python

import os
import sys
import setuptools.command.egg_info as egg_info_cmd

from setuptools import setup, find_packages

SETUP_DIR = os.path.dirname(__file__) or '.'

try:
    import gittaggers
    tagger = gittaggers.EggInfoFromGit
except ImportError:
    tagger = egg_info_cmd.egg_info

setup(name='tail_job_logs',
      version='0.1',
      description='read crunch log files',
      author='sguthrie',
      author_email='sguthrie@curoverse.com',
      download_url="https://github.com/sguthrie/arvados-tools.git",
      license='GNU Affero General Public License, version 3.0',
      packages=['tail_job_logs'],
      include_package_data=True,
      scripts=[
          'bin/tail-job-logs'
      ],
      data_files=[
          ('share/doc/tail-job-logs', ['agpl-3.0.txt']),
      ],
      install_requires=[
          'arvados-python-client',
      ],
      zip_safe=False,
      cmdclass={'egg_info': tagger},
      )
