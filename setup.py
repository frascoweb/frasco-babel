from setuptools import setup


def desc():
    with open("README.md") as f:
        return f.read()

def reqs():
    with open('requirements.txt') as f:
        return f.read().splitlines()

setup(
    name='frasco-babel',
    version='0.1',
    url='http://github.com/frascoweb/frasco-babel',
    license='MIT',
    author='Maxime Bouroumeau-Fuseau',
    author_email='maxime.bouroumeau@gmail.com',
    description="I18n and L10n support for Frasco",
    long_description=desc(),
    py_modules=['frasco_babel'],
    platforms='any',
    install_requires=reqs() + ['frasco']
)