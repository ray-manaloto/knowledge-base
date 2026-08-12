---
source_url: "https://docs.doppler.com/docs/docker-compose.md"
content_sha256: f214ddf9bed95edca31a5d09cf8d9c94ad5ab193727277d0ca58ab2f42510313
content_chars: 8899
---

---
updatedAt: 2025-09-25T17:43:30.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# Docker Compose

This guide will show you two methods of using Doppler to supply app config and secrets for Docker Compose in production and local development environments.

| Option                                                 | Usecase                                                    |
| :----------------------------------------------------- | :--------------------------------------------------------- |
| **[Dockerfile](#option-1-dockerfile)**                 | Installs the Doppler CLI in the Dockerfile.                |
| **[Container Env Vars](#option-2-container-env-vars)** | Secrets injected into containers as environment variables. |

## Prerequisites

* You've run applications in Docker Compose and have experience building Docker images.

## Service Tokens

Accessing your secrets in production or CI/CD environments requires a  [Service Token](https://docs.doppler.com/docs/service-tokens) to provide read-only access to a specific config. It's exposed to the CLI via the `DOPPLER_TOKEN` environment variable which should be provided by your CI/CD environment, e.g. GitHub Secret.

## Option 1: Dockerfile

This option embeds the Doppler CLI in a `Dockerfile` and requires the `DOPPLER_TOKEN` environment variable. Save this as `Dockerfile`:

```dockerfile Debian/Ubuntu
FROM ubuntu

# Install Doppler CLI
RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && \
    apt-get -y install doppler
    
# Fetch and view secrets using "printenv". Testing purposes only!
# Replace "printenv" with the command used to start your app, e.g. "npm", "start"
CMD ["doppler", "run", "--", "printenv"]
```
```dockerfile Alpine
FROM alpine

# Install Doppler CLI
RUN wget -q -t3 'https://packages.doppler.com/public/cli/rsa.8004D9FF50437357.key' -O /etc/apk/keys/cli@doppler-8004D9FF50437357.rsa.pub && \
    echo 'https://packages.doppler.com/public/cli/alpine/any-version/main' | tee -a /etc/apk/repositories && \
    apk add doppler

# Fetch and view secrets using "printenv". Testing purposes only!
# Replace "printenv" with the command used to start your app, e.g. "npm", "start"
CMD ["doppler", "run", "--", "printenv"]
```
```dockerfile RedHat/CentOS
FROM centos

# Install Doppler CLI
RUN rpm --import 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/config.rpm.txt' | tee /etc/yum.repos.d/doppler-cli.repo && \
    yum update -y && \
    yum install -y doppler

# Fetch and view secrets using "printenv". Testing purposes only!
# Replace "printenv" with the command used to start your app, e.g. "npm", "start"
CMD ["doppler", "run", "--", "printenv"]
```
```dockerfile Shell Script
FROM alpine

# Option 1: Standard
RUN (curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh || wget -t 3 -qO- https://cli.doppler.com/install.sh) | sh

# Option 2: Signature Verification (GnuPG package required)
RUN (curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh || wget -t 3 -qO- https://cli.doppler.com/install.sh) | sh -s -- --verify-signature

# Fetch and view secrets using "printenv". Testing purposes only!
# Replace "printenv" with the command used to start your app, e.g. "npm", "start"
CMD ["doppler", "run", "--", "printenv"]
```

Then save the below file as `docker-compose.yml`:

```yaml docker-compose.yml
services:
  web:
    build: .
    image: doppler-test-alpine
    container_name: doppler-test
    init: true
    environment:
      - DOPPLER_TOKEN
```

### Production deployments

A Doppler [Service Token](https://docs.doppler.com/docs/service-tokens) exposed as the `DOPPLER_TOKEN` environment variable provides read-only access to a specific config in production environments:

```shell
# Expects the `DOPPLER_TOKEN` environment variable
docker-compose up
```

#### Multiple Services

If you're using multiple services in your compose file and need to pass in multiple Doppler tokens, you can accomplish that by passing in multiple tokens and mapping them in your `docker-compose.yml` file. To do that, you would execute a command like this:

```shell
# make sure you adjust the `--max-age` value appropriately
DOPPLER_TOKEN_API="$(doppler configs tokens create --project api --config dev api-dev-token --plain --max-age 1m)" \
DOPPLER_TOKEN_WEB="$(doppler configs tokens create --project web --config dev web-dev-token --plain --max-age 1m)" \
docker-compose -f docker-compose.yml up
```

The above dynamically generates two Doppler tokens for two separate projects and configs with a TTL specified with the `--max-age` flag (make sure you adjust that how you need). You would then update your `docker-compose.yml` file to look something like this:

```yaml docker-compose.yml
services:
  api:
    build: .
    image: doppler-test-alpine
    container_name: doppler-test-api
    init: true
    environment:
      - DOPPLER_TOKEN=${DOPPLER_TOKEN_API}
  web:
    build: .
    image: doppler-test-alpine
    container_name: doppler-test-web
    init: true
    environment:
      - DOPPLER_TOKEN=${DOPPLER_TOKEN_WEB}
```

### Local development

For local development, pass your CLI token in as `DOPPLER_TOKEN`:

```shell
DOPPLER_TOKEN="$(doppler configure get token --plain)" \
docker-compose -f docker-compose.yml up
```

> 📘
>
> This method requires your `doppler run` commands specify a project and config using the `-p` and `-c` flags.

In a multiple service situation, to mirror production you can just pass the same token in multiple times:

```shell
DOPPLER_TOKEN_API="$(doppler configure get token --plain)" \
DOPPLER_TOKEN_WEB="$(doppler configure get token --plain)" \
docker-compose -f docker-compose.yml up
```

## Option 2: Container Env Vars

Alternatively, you can use the Doppler CLI to supply environment variables to Docker Compose with each container explicitly defining which environment variables they wish to receive. The benefit of this approach is that Docker Compose is run the same in development as it is in production.

Here is a `docker-compose.yml` that will pass on the three standard Doppler environment variables as well as two custom variables:

> 📘
>
> Only environment variables explicitly listed in the `environment:` map will be passed through to the container.
>
> Make sure you update this list any time you add a new secret to your Doppler project.

```yaml docker-compose.yml
services:
  web:
    build: .
    image: alpine
    container_name: doppler-test
    init: true
    environment:
      - API_KEY
      - OTHER_SECRET
```

Then use the Doppler CLI to inject the environment variables:

```shell
doppler run -- docker-compose up
```

### Dynamic Environment List

Explicitly defining the environment variables for a container is ideal, but it's also possible to auto-populate the list of environment variables at runtime.

This method allows you to create a `doppler-env` block containing the environment variable names from Doppler that can be injected anywhere in your `docker-compose.yml` file.

To use this method, rename your existing `docker-compose.yml` file to `doppler-docker-compose.yml` and replace the entire `environment:` block for any services you want to use this for with a reference to the extension field rendered by the Doppler CLI:

```Text Multiple Services
x-doppler: &doppler-env
  environment:{{range $key, $value := .}}
    - {{$key}}{{end}}

services:
  web:
    image: web
    command: npm start
    <<: *doppler-env
    ports:
      - '8080:8080'
  api:
    image: api
    command: ./app-start.sh
    <<: *doppler-env
    ports:
      - '9090:9090'
```
```yaml Single Service
services:
  web:
    image: web
    command: npm start
    # Ignore editor syntax errors. Produces valid YAML
    environment:{{range $key, $value := .}}
      - {{$key}}{{end}}
    ports:
      - '8080:8080'    
```

Then inject secrets into the ephemeral `docker-compose.yml` file:

```shell
doppler run \
    --mount docker-compose.yml \
    --mount-template doppler-docker-compose.yml \
    --command 'doppler run -- docker-compose up'
```

> 👍 Amazing Work!
>
> Now you know two methods for Doppler to supply app config and secrets for Docker Compose in production and local development environments.