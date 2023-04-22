from distutils.core import setup

from setuptools import find_packages

setup(
    name="solidifi",
    version="0.0.2",
    packages=find_packages(),
    install_requires=["matplotlib", "ijson", "numpy", "configparser", "pandas"],
    zip_safe=False,
    entry_points={"console_scripts": ["solidifi = solidifi.__main__:main"]},
    py_modules=["solidifi"],
)
