from setuptools import setup, find_packages

setup(
    name="tdf_data_bridge",
    version="1.0.0",
    description="ProForm TDF Bike Control via ANT+ and BLE FTMS",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "bleak==0.21.1",
        "openant==0.2.0",
        "pyserial==3.5"
    ],
    entry_points={
        "console_scripts": [
            "tdf-bridge = tdf_data_bridge:main"
        ]
    },
)
