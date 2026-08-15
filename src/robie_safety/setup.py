from setuptools import find_packages, setup

package_name = 'robie_safety'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kene',
    maintainer_email='keneayogu@gmail.com',
    description='Safety interlock and E-stop logic for R.O.B.I.E.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'safety_node = robie_safety.safety_node:main',
        ],
    },
)
