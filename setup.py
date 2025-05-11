from setuptools import setup, find_packages

install_requires = [
    "accelerate>=1.6.0",
    "gradio>=5.29.0",
    "mlx_lm>=0.24.0",
    "numpy>=2.2.5",
    "pillow>=11.2.1",
    "pyyaml>=6.0.2",
    "transformers>=4.51.3",
    "torch==2.3.0",
]

setup(
    name="CYTOLONE",
    version="0.0.1",
    packages=find_packages(),
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "cytolone = CYTOLONE.app:run",
            "cytolone-config = CYTOLONE.default_config.config_manager:main",
            "scale-check = CYTOLONE.scale_check.scale_checker:run",
            "download-model = CYTOLONE.download_models:main"
        ]
    }
)