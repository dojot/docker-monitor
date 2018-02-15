# -*- coding: utf-8 -*-
#https://packaging.python.org/tutorials/distributing-packages/
import os

#https://pythonhosted.org/versiontools/usage.html
import setuptools

from pip import download
from pip import req


HERE = os.path.dirname(os.path.abspath(__file__))


def get_requirements(file):
    path = os.path.join(HERE, file)
    deps = list()
    for dep in req.parse_requirements(path, session=download.PipSession()):
        try:
            # Pip 8.1.2 Compatible
            specs = ','.join(''.join(str(spec)) for spec in dep.req.specifier)
        except AttributeError:
            # Pip 1.5.4 Compatible
            specs = ','.join(''.join(spec) for spec in dep.req.specs)
        requirement = '{name}{extras}{specs}'.format(
            name=dep.name,
            extras=(
                '[{extras}]'.format(extras=','.join(dep.extras))
                if dep.extras else ''
            ),
            specs=specs,
        )

        deps.append(requirement)
    return deps


setuptools.setup(
    name='dockermon',
    description='Dojot docker monitor.',
    version=':versiontools:dockermon:',

    packages=setuptools.find_packages(exclude=['docs', 'tests']),
    include_package_data=True,
    install_requires=get_requirements('requirements.txt'),
    setup_requires='versiontools',

    author='Rafael Augusto Scaraficci',
    author_email='raugusto@cpqd.com.br',
    url='dojot.com.br',
)

