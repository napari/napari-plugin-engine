from setuptools import setup

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: MacOS :: MacOS X",
    "Topic :: Software Development :: Testing",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
] + [
    ("Programming Language :: Python :: %s" % x) for x in "3.6 3.7 3.8".split()
]

with open("README.md", "rb") as fd:
    long_description = fd.read().decode("utf-8")

with open("CHANGELOG.rst", "rb") as fd:
    long_description += "\n\n" + fd.read().decode("utf-8")

EXTRAS_REQUIRE = {
    "dev": ["pre-commit", "tox"],
    "testing": ["pytest"],
}


def main():
    setup(
        name="napari-plugin-engine",
        description="napari plugin engine, fork of pluggy",
        long_description=long_description,
        long_description_content_type='text/markdown',
        license="MIT license",
        author="napari team",
        url="https://github.com/napari/napari-plugin-engine",
        python_requires=">=3.6.*",
        install_requires=['importlib-metadata>=0.12;python_version<"3.8"'],
        extras_require=EXTRAS_REQUIRE,
        setup_requires=["setuptools-scm"],
        use_scm_version={"write_to": "napari_plugin_engine/_version.py"},
        classifiers=classifiers,
        packages=["napari_plugin_engine"],
        entry_points={
            "pytest11": [
                "napari-plugin-engine = napari_plugin_engine._testsupport"
            ]
        },
    )


if __name__ == "__main__":
    main()
