from setuptools import setup
from glob import glob
setup(name='robie_bringup', version='0.1.0', packages=['robie_bringup'], data_files=[('share/ament_index/resource_index/packages', ['resource/robie_bringup']), ('share/robie_bringup', ['package.xml']), ('share/robie_bringup/launch', glob('launch/*.launch.py'))], install_requires=['setuptools'], maintainer='th0r12f4t', maintainer_email='th0r12f4t@users.noreply.github.com', description='R.O.B.I.E. bringup: safety bridge and web bridge', license='MIT', entry_points={'console_scripts': ['web_bridge = robie_bringup.web_bridge:main']})
