FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app
COPY pyproject.toml .

# Install dependencies - added matplotlib and adlfs here
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        dagster \
        dagster-postgres \
        dagster-k8s \
        dagster-azure \
        azure-identity \
        geopandas shapely pyarrow matplotlib \
        adlfs

COPY hydrosat_project ./hydrosat_project
COPY workspace.yaml .

# Use module loading
CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-m", "hydrosat_project"]