from setuptools import setup, find_packages

setup(
    name='pycloudfn',
    version='0.2',
    description='GCP Cloud functions in python',
    url='https://github.com/MartinSahlen/cloud-functions-python',
    author='Martin Sahlen',
    author_email='martin8900@gmail.com',
    license='MIT',
    entry_points={
        'console_scripts': ['py-cloud-fn=cloudfn.cli:main'],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    install_requires=[
        'pyinstaller',
        'python-dateutil',
        'six',
        'Jinja2',
        'pyspin',
        'google-auth',
    ],
    include_package_data=True,
    packages=find_packages(exclude=['examples*', 'docs', 'build', ]),
    zip_safe=False
)
