from pathlib import Path

from setuptools import find_packages, setup

setup(
    name="outlook-signature-manager",
    version="0.1.0",
    description="Manage Outlook signatures for a Microsoft 365 tenant",
    packages=find_packages(include=["src", "src.*"]),
    package_data={"src": ["powershell/*.ps1"]},
    python_requires=">=3.10",
    install_requires=[
        line.strip()
        for line in Path(__file__).with_name("requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ],
)
