from setuptools import find_packages, setup

package_name = 'arm_commissioning'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Alexander Christensen',
    maintainer_email='almc@teknologisk.dk',
    description='Idriftsættelses- og testværktøjer for en enkelt humanoid-arm.',
    license='Teknologisk Institut',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'calibration_tool_node = arm_commissioning.calibration_tool_node:main',
            'step_response_node = arm_commissioning.step_response_node:main',
            'repeatability_node = arm_commissioning.repeatability_node:main',
        ],
    },
)
