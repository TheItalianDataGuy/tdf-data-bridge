from setuptools import setup, find_packages

setup(
    name="tdf_data_bridge",
    version="1.0.0",
    description="ProForm TDF Bike Control via ANT+ and BLE FTMS",
    author="TheItalianDataGuy",
    packages=find_packages(),
    install_requires=[
        "bleak==0.22.3",
        "openant==1.3.3",
        "pyserial==3.5",
    ],
    license="MIT",
    url="https://github.com/TheItalianDataGuy/tdf-data-bridge.git",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    entry_points={
        "console_scripts": [
            "tdf-bridge = tdf_data_bridge:main"
        ]
    },
)
