from setuptools import setup
import os
from glob import glob

package_name = 'robie_vision'

setup(
 name=package_name,
 version='0.1.0',
 packages=[package_name],
 data_files=[
 ('share/ament_index/resource_index/packages',
 ['resource/' + package_name]),
 ('share/' + package_name, ['package.xml']),
 (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
 (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
 ],
 install_requires=['setuptools'],
 zip_safe=True,
 maintainer='th0r12f4t',
 maintainer_email='keneayogu@gmail.com',
 description='Camera and vision processing for R.O.B.I.E.',
 license='MIT',
 tests_require=['pytest'],
 entry_points={
 'console_scripts': [
 'camera_node = robie_vision.camera_node:main',
 'crack_detector_node = robie_vision.crack_detector_node:main',
 ],
 },
)
