---
source_url: "https://docs.doppler.com/docs/docker-high-availability.md"
content_sha256: 38a55ab545ecdb1a6e5c764ecf8a55080d7a79aabccb00d127a5922ce8095215
content_chars: 4358
---

---
updatedAt: 2025-10-07T17:52:58.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# High Availability

Increase resiliency when using the Doppler CLI in Docker by embedding an encrypted secrets snapshot.

## Prerequisites

* You've run applications in Docker and have experience building Docker images.

## Service Tokens

Accessing your secrets in production or CI/CD environments requires a  [Service Token](https://docs.doppler.com/docs/service-tokens) to provide read-only access to a specific config. It's exposed to the CLI via the `DOPPLER_TOKEN` environment variable which should be provided by your CI/CD environment, e.g. GitHub Secret.

<Callout icon="🚧" theme="warn">
  Decrypting the snapshot file is only possible if the `DOPPLER_TOKEN` value at runtime matches the value used at build time or if you use the `--passphrase` flag (or `DOPPLER_PASSPHRASE` environment variable) when generating it and pass in the correct passphrase when decrypting the snapshot.
</Callout>

## Installation

In the [rare event](https://www.dopplerstatus.com/uptime) that Doppler is down, you can optionally add high availability to your Docker images by creating an encrypted snapshot of the secrets at build time. This also allows images to be built for specific environments that do not require network access to the Doppler API as the Doppler CLI will fall back to the saved encrypted snapshot.

<Callout icon="🚧" theme="warn">
  Using this method will embed a snapshot of your config's secrets in the image. This image is now dedicated to that config and should not be reused across environments.
</Callout>

Let's see a full example of a Dockerfile with high availability:

```dockerfile ENTRYPOINT
FROM alpine

# Install the Doppler CLI
RUN wget -q -t3 'https://packages.doppler.com/public/cli/rsa.8004D9FF50437357.key' -O /etc/apk/keys/cli@doppler-8004D9FF50437357.rsa.pub && \
  echo 'https://packages.doppler.com/public/cli/alpine/any-version/main' | tee -a /etc/apk/repositories && \
  apk add doppler

# Pass `DOPPLER_TOKEN` at build time to create an encrypted snapshot for high-availability
ARG DOPPLER_TOKEN

# Create encrypted snapshot for high availability
RUN doppler secrets download doppler.encrypted.json

# Fetch secrets and print them using "printenv" command
ENTRYPOINT ["doppler", "run", "--fallback=doppler.encrypted.json", "--"]
CMD ["your-command-here"]
```
```dockerfile CMD
FROM alpine

# Install the Doppler CLI
RUN wget -q -t3 'https://packages.doppler.com/public/cli/rsa.8004D9FF50437357.key' -O /etc/apk/keys/cli@doppler-8004D9FF50437357.rsa.pub && \
  echo 'https://packages.doppler.com/public/cli/alpine/any-version/main' | tee -a /etc/apk/repositories && \
  apk add doppler

# Pass `DOPPLER_TOKEN` at build time to create an encrypted snapshot for high-availability
ARG DOPPLER_TOKEN

# Create encrypted snapshot for high availability
RUN doppler secrets download doppler.encrypted.json

# Fetch secrets and print them using "printenv" command
CMD ["doppler", "run", "--fallback=doppler.encrypted.json", "--", "your-command-here"]
```

> ❗️ Use Persistent Storage
>
> The fallback file should always be saved on persistent storage to avoid scenarios where a deployment or restart may occur resulting in the file being lost.

> 🚧 Hitting Rate Limits?
>
> Fallback files also offer protection against exceeding Doppler API’s 240 requests/minute rate limit which can occur when using images on Serverless infrastructure such as [AWS Lambda](https://aws.amazon.com/lambda/) and [CloudRun](https://cloud.google.com/run). We recommend setting the `--fallback-only` flag on the `doppler run` command in the `ENTRYPOINT` under those scenarios.

The `DOPPLER_TOKEN` is then passed in as a `build-arg` when building the image since it is used as the encryption key for the fallback file:

```shell Terminal
docker build --build-arg "DOPPLER_TOKEN=$DOPPLER_TOKEN" -t doppler-ha .
```

Now that you have an image built, the last step is to run it with the `DOPPLER_TOKEN`. The `DOPPLER_TOKEN` is needed as it is used to decrypt the fallback file.

```shell Terminal
docker run -e "DOPPLER_TOKEN=$DOPPLER_TOKEN" doppler-ha
```

> 👍 Amazing Work!
>
> Your secrets in Doppler are now ready to be used in your Docker containers.