
# -*- coding: utf-8 -*-

# DO NOT EDIT THIS FILE!
# This file has been autogenerated by dephell <3
# https://github.com/dephell/dephell

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

readme = ''

setup(
    long_description=readme,
    name='read-a-script',
    version='0.1.0',
    description='Mac: Read a play script in various voices, to help with line learning.',
    python_requires='==3.*,>=3.9.0',
    author='Neil Padgen',
    author_email='neil.padgen@gmail.com',
    license='BSD',
    entry_points={"console_scripts": ["script_learner = read_a_script.script_learner:main"]},
    packages=['read_a_script'],
    package_dir={"": "."},
    package_data={},
    install_requires=['docopt==0.*,>=0.6.2', 'jouvence==0.*,>=0.4.2', 'pyttsx3==2.*,>=2.90.0', 'readchar==2.*,>=2.0.1', 'ruamel.yaml==0.*,>=0.16.12'],
    extras_require={"dev": ["dephell==0.*,>=0.8.3", "ipython==7.*,>=7.19.0", "jupyter==1.*,>=1.0.0"]},
)