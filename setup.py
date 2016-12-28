from setuptools import setup, find_packages


setup(
    name='frasco-babel',
    version='0.4.4',
    url='http://github.com/frascoweb/frasco-babel',
    license='MIT',
    author='Maxime Bouroumeau-Fuseau',
    author_email='maxime.bouroumeau@gmail.com',
    description="I18n and L10n support for Frasco",
    packages=find_packages(),
    zip_safe=False,
    platforms='any',
    install_requires=[
        'frasco',
        'Flask-Babel>=0.9',
        'goslate>=1.3.0'
    ]
)
