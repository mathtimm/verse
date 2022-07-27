from pathlib import Path
from setuptools import find_packages, setup

HERE = Path(__file__).parent
README = (HERE / "README.md").read_text(encoding='utf-8')

setup(
    name="verse",
    version="0.0.1",
    author="Mathilde Timmermans",
    description="Annex to prose package for TESS reporting",
    packages=find_packages(exclude=["test"]),
    #include_package_data = True,
    license="MIT",
    url="https://github.com/mathtimm/verse",
    # entry_points="""
    #     [console_scripts]
    #     prose=main:cli
    # """,
    long_description=README,
    long_description_content_type="text/markdown",
    install_requires=[
        "prose",
        "exoplanet",
        "pymc3",
        "pymc3_ext"
    ],
    extras_require={
        'docs': [
            "sphinx",
            "nbsphinx",
            "jupyter-sphinx",
            "sphinx_rtd_theme",
            "sphinx-copybutton",
            "docutils",
            "jupyterlab",
            "myst-parser",
            "twine",
        ]
    },
    zip_safe=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
