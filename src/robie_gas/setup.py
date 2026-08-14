from setuptools import find_packages, setup

package_name = 'robie_gas'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='th0r12f4t',
    maintainer_email='th0r12f4t@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
		'gas_climber = robie_gas.gas_climber:main',
		'plume_sim = robie_gas.plume_sim:main',
		'roc_harness = robie_gas.roc_harness:main',
        ],
    },
)
