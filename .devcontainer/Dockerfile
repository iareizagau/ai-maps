# Heredar de la imagen base del proyecto (que ya tiene instaladas las librerías GIS y dependencias de Python)
FROM maps-app:latest

USER root

# Instalar utilidades de desarrollo (git para control de versiones, procps para herramientas de VS Code, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    sudo \
    curl \
    wget \
    openssh-client \
    procps \
    ca-certificates \
    tar \
    coreutils \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app
