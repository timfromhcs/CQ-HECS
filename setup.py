from setuptools import setup, find_packages

setup(
    name="cqhecs",
    version="0.1.0",
    description="CQ-HECS: Deterministic Classical Four-Path Quantum Circuit Simulation Engine",
    author="timfromhcs",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "qiskit",
    ],
    python_requires=">=3.9",
)
