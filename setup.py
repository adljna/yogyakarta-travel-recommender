"""Setup configuration untuk itinerary-recommendation-system."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="itinerary-recommendation-system",
    version="0.1.0",
    author="Data Science Team",
    description="AI-powered travel itinerary recommendation system untuk Indonesia",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/itinerary-recommendation-system",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
    ],
    python_requires=">=3.10",
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.4.0",
        "pydantic-settings>=2.0.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "geopandas>=0.13.0",
        "requests>=2.31.0",
        "SPARQLWrapper>=2.0.0",
        "neo4j>=5.13.0",
        "anthropic>=0.7.0",
        "fastapi>=0.103.0",
        "uvicorn>=0.23.0",
        "python-dateutil>=2.8.0",
        "fuzzywuzzy>=0.18.0",
        "python-Levenshtein>=0.21.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.0.0",
            "mypy>=1.4.0",
        ],
        "jupyter": [
            "jupyter>=1.0.0",
            "ipython>=8.14.0",
            "matplotlib>=3.7.0",
            "seaborn>=0.12.0",
            "folium>=0.14.0",
        ],
    },
)
