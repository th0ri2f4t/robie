from setuptools import find_packages, setup

package_name = 'robie_nav'

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
    maintainer='th0r12f4t',
    maintainer_email='keneayogu@gmail.com',
    description='Navigation and locomotion for R.O.B.I.E.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mecanum_driver = robie_nav.mecanum_driver:main',
        ],
    },
)
