"""Package setup for DevVisionFlow Prototype 2."""

from setuptools import setup, find_packages

setup(
    name="devvisionflow-prototype-2",
    version="0.1.0",
    description="Air Gesture-Controlled File Transfer System",
    author="NeilhancyDev78",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests"]),
    install_requires=[
        "mediapipe>=0.10.0",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
    ],
    extras_require={
        "encryption": ["cryptography>=41.0.0"],
        "sound": ["pygame>=2.5.0"],
        "pdf": ["PyMuPDF>=1.23.0"],
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "dvf-sender=sender.main:main",
            "dvf-receiver=receiver.main:main",
        ],
    },
)
