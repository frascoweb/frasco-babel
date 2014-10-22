from setuptools import setup


setup(
    name='frasco-babel',
    version='0.1',
    url='http://github.com/frascoweb/frasco-babel',
    license='MIT',
    author='Maxime Bouroumeau-Fuseau',
    author_email='maxime.bouroumeau@gmail.com',
    description="I18n and L10n support for Frasco",
    py_modules=['frasco_babel'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        # 'frasco',
        'Flask-Babel>=0.9',
        'goslate>=1.3.0'
    ]
)