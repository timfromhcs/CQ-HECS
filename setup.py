from setuptools import setup, find_packages

setup(
    name="cqhecs",
    version="4.5.0",
    description="CQ-HECS: Bit-Exact Giles-Selinger Ring & Hybrid Stabilizer-MPS Quantum Computing Engine",
    author="timfromhcs",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "qiskit",
    ],
    python_requires=">=3.9",
)
