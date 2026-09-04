from setuptools import setup, find_packages

setup(
    name="cqhecs",
    version="0.2.0",
    description="CQ-HECS: Deterministic Classical Four-Path Quantum Circuit Simulation Engine",
    author="timfromhcs",
    license="Apache-2.0",
    packages=find_packages(include=["cqhecs*", "python_bridge*"], exclude=["tests*", "benchmarks*", "audit*"]),
    install_requires=[
        "numpy>=1.24.0",
        "qiskit>=0.45.0",
    ],
    python_requires=">=3.9",
)
