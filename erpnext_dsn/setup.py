from setuptools import setup, find_packages

setup(
    name="erpnext_dsn",
    version="0.1.0",
    description="DSN phase 3.1 monthly payroll declaration for ERPNext (French insurance IS)",
    author="AndreLiar",
    author_email="andrelaurelyvan.kanmegnetabouguie@ynov.com",
    packages=find_packages(),
    install_requires=["requests"],
    zip_safe=False,
)
