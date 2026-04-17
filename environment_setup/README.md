# STANDALONE-VTA Development Environment (Docker)

This repository provides a `Dockerfile` to set up a **reproducible research environment** for working with the **STANDALONE-VTA (Versatile Tensor Accelerator)**. 

## Prerequisites

- **Docker** installed on your host machine.
- Internet access. If you are behind a corporate firewall, refer to the Proxy Configuration section below.
- **Vivado 2025.2** installed on your host machine if you want to perform FPGA implementation.

## Building the Image

### Standard Build (Direct Connection)
If you are working from a home network or an open academic network, execute this command from the project root folder:
```bash
docker build \
  -t standalone-vta \
  -f environment_setup/Dockerfile .
```

### Build with Proxy (Restricted Environments)
If your network requires a proxy, you must pass the proxy settings as **build arguments** to configure both the system environment and the JVM. Adapt and execute this command from the project root folder:

```bash
docker build \
  --build-arg HTTP_PROXY="http://<PROXY_HOST>:<PORT>" \
  --build-arg HTTPS_PROXY="http://<PROXY_HOST>:<PORT>" \
  --build-arg PROXY_JVM_OPTS="-Dhttp.proxyHost=<PROXY_HOST> -Dhttp.proxyPort=<PORT> -Dhttps.proxyHost=<PROXY_HOST> -Dhttps.proxyPort=<PORT>" \
  -t standalone-vta \
  -f environment_setup/Dockerfile .
```

> **Note:** Leaving these arguments empty will default the image to a "no-proxy" configuration.

## Running the Container

### Simple Execution (Interactive)
To launch the development environment, execute the following command from the project root. This setup ensures that file permissions remain consistent between the container and your host.

```bash
docker run -it --rm \
  --user $(id -u):$(id -g) \
  -v $(pwd):/workspace/standalone-vta \
  -w /workspace/standalone-vta \
  standalone-vta
```

### Advanced Hardware Options
If you are moving beyond simulation to **FPGA implementation**, you need to map your local Xilinx tools and licenses:

* **Xilinx Tools**: Add `-v /opt/Xilinx:/opt/Xilinx:ro` to access Vivado/Vitis. The `:ro` flag ensures the container cannot accidentally modify your host installation.
* **License Mapping**: If your target device requires a specific license, map your license file or directory (e.g., `-v ~/.Xilinx:/home/user/.Xilinx:ro`) or pass the environment variable using `-e XILINXD_LICENSE_FILE=<port>@<server>`.

**Example with FPGA support:**
```bash
docker run -it --rm \
  --user $(id -u):$(id -g) \
  -v $(pwd):/workspace/standalone-vta \
  -v /opt/Xilinx:/opt/Xilinx:ro \
  -e XILINXD_LICENSE_FILE=2100@license-server \
  -w /workspace/standalone-vta \
  standalone-vta
```

## Software Stack

| Tool | Version | Description |
| :--- | :--- | :--- |
| **Ubuntu** | 24.04 | Base operating system |
| **OpenJDK** | 21 | Java Runtime for Chisel/Scala |
| **Mill** | (via project) | Build tool for VTA hardware generation |

## Troubleshooting

**JVM fails to download dependencies (Mill):**
Verify that the proxy environment variables `HTTP_PROXY`, `HTTPS_PROXY` and `PROXY_JVM_OPTS` were correctly passed during the build stage.

## Next Steps
Once your environment is set up and running, refer to the root [README.md](../README.md).