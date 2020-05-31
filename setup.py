

from setuptools import setup, find_packages

package_name = 'netcfgbu'
package_version = open('VERSION').read().strip()


def requirements(filename='requirements.txt'):
    return open(filename.strip()).readlines()


with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
    name=package_name,
    version=package_version,
    description='Network Configuration Backup',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Jeremy Schulman',
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements()
)