# STANDALONE-VTA Development Environment (Docker)

This repository provides a `Dockerfile` to set up a **reproducible research environment** for working with the **STANDALONE-VTA (Versatile Tensor Accelerator)**. 

## 🛠 Prerequisites

- **Docker** installed on your host machine.
- Internet access. If you are behind a corporate firewall, refer to the Proxy Configuration section below.

## 🚀 Building the Image

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

## 💻 Running the Container

To launch the container in interactive mode and mount your local workspace, execute this command from the project root folder:

```bash
docker run -it --rm \
  -v $(pwd):/workspace/standalone-vta \
  standalone-vta
```

Flags:
- `--rm`: Automatically removes the container upon exit to keep your system clean.
- `-v`: Maps your local `standalone-vta` directory to the container's workspace.

## 🏗 Software Stack

| Tool | Version | Description |
| :--- | :--- | :--- |
| **Ubuntu** | 24.04 | Base operating system |
| **OpenJDK** | 21 | Java Runtime for Chisel/Scala |
| **Mill** | (via project) | Build tool for VTA hardware generation |

## 🔍 Troubleshooting

**JVM fails to download dependencies (Mill):**
Verify that the proxy environment varaibles `HTTP_PROXY`, `HTTP_PROXY` and `PROXY_JVM_OPTS` were correctly passed during the build stage.
