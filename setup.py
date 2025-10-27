from setuptools import find_packages, setup

package_name = 'pupper_llm'

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
    maintainer='Gabrael Levine',
    maintainer_email='gabrael@cs.stanford.edu',
    description='LLM integration for the Pupper robot',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'pupper_llm_node = pupper_llm.pupper_llm_node:main'
        ],
    },
)
