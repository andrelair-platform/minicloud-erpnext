from setuptools import setup, find_packages

setup(
    name="erpnext_sepa",
    version="1.0.0",
    description="SEPA Direct Debit integration for ERPNext — GoCardless mandate + PAIN.008",
    packages=find_packages(),
    zip_safe=False,
)
