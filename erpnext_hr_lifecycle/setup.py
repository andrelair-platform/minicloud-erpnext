from setuptools import find_packages, setup

setup(
    name="erpnext_hr_lifecycle",
    version="0.1.0",
    description="Joiner/Mover/Leaver lifecycle event emission for the ktayl-solution HR IS "
    "(ERPNext → signed NATS JetStream + n8n non-access fan-out)",
    packages=find_packages(),
    zip_safe=False,
)
