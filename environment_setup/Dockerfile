FROM nvcr.io/nvidia/pytorch:26.02-py3
# Latest Nvidia image based on Ubuntu 24.04
# Pytorch 2.11.0 (https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-26-02.html#rel-26-02)

ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG PROXY_JVM_OPTS=""

ENV DEBIAN_FRONTEND=noninteractive

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV PROXY_JVM_OPTS=${PROXY_JVM_OPTS}

ENV JAVA_TOOL_OPTIONS=${PROXY_JVM_OPTS}
ENV JAVA_OPTS=${PROXY_JVM_OPTS}
ENV MILL_JVM_OPTS=${PROXY_JVM_OPTS}

ENV MILL_VERSION=1.1.4-jvm
ENV VERILATOR_VERSION=5.046

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk \
    help2man \
    flex \
    bison \
    ccache \
    libgoogle-perftools-dev \
    libjemalloc-dev \
    perl-doc \
    libfl2 \
    libfl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN cd /opt \
    && git clone --depth 1 --branch v${VERILATOR_VERSION} https://github.com/verilator/verilator \
    && unset VERILATOR_ROOT \
    && cd verilator \
    && autoconf \
    && ./configure \
    && make -j4 \
    && make install

COPY environment_setup/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

WORKDIR /workspace/standalone-vta

# Copy the wrapper script to trigger the download of the Mill binary during build time.
# This ensures the environment is ready and the version is cached in the image.
COPY src/simulators/cycle_accurate_simulator/mill /tmp/mill
RUN chmod +x /tmp/mill && /tmp/mill --version && rm /tmp/mill

CMD ["/bin/bash"]
