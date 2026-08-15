from setuptools import find_packages, setup

package_name = 'robie_hardware'

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
    description='Pi-side serial bridge to the ESP32 spinal cord',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'serial_bridge = robie_hardware.serial_bridge_node:main',
        ],
    },
)
