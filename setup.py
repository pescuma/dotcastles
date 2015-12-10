from distutils.core import setup

setup(
    name='dotcastles',
    packages=['dotcastles'],
    version='0.1',
    description='Shares your dotcastles through git',
    author='Ricardo Pescuma Domenecci',
    author_email='ricardo@pescuma.org',
    url='https://github.com/pescuma/dotcastles',
    download_url='https://github.com/pescuma/dotcastles/tarball/v0.1',
    keywords=['dotcastles'],
    classifiers=[],
    entry_points={
        'console_scripts': [
            'dotcastles = dotcastles:main'
        ]
    },
)
