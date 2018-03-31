from setuptools import setup

setup(
    name='dotcastles',
    packages=['dotcastles'],
    version='0.1.4',
    description='Shares your dotfiles through git',
    author='Ricardo Pescuma Domenecci',
    author_email='ricardo@pescuma.org',
    license='GPL',
    url='https://github.com/pescuma/dotcastles',
    download_url='https://github.com/pescuma/dotcastles/tarball/v0.1.4',
    keywords=['dotfiles'],
    classifiers=[],
    entry_points={
        'console_scripts': [
            'dotcastles=dotcastles.dotcastles:main'
        ]
    },
    install_requires=['gitpython'],
)
