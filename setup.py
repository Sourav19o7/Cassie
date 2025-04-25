from setuptools import setup, find_packages

setup(
    name="empathic-solver",
    version="1.3.0",  # Updated version with WhatsApp integration
    py_modules=["empathic_solver", "reminders", "whatsapp_integration"],  # Added whatsapp_integration module
    include_package_data=True,
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.4.2",
        "pandas>=2.0.3",
        "numpy>=1.24.3",
        "requests>=2.28.0",
        "keyring>=23.0.0",
        "schedule>=1.2.0",
        "selenium>=4.0.0",
        "webdriver-manager>=3.8.0",
        "pillow>=9.0.0",
    ],
    entry_points="""
        [console_scripts]
        empathic-solver=empathic_solver:app
        cassie=empathic_solver:app
    """,
    python_requires=">=3.8",
    author="Sourav Dey",
    author_email="sourav.dey147@gmail.com",
    description="A CLI tool for empathetic problem-solving with metrics tracking, reminders, and WhatsApp integration, powered by Claude Haiku",
    keywords="cli, problem-solving, metrics, productivity, ai, claude, reminders, whatsapp",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)