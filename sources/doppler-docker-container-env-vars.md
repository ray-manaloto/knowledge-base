---
source_url: "https://docs.doppler.com/docs/docker-container-env-vars.md"
content_sha256: d8740a9a10ce590a94562bd8655681a1516c93c8cd79af2cc0a5ea766000fb83
content_chars: 1722
---

---
updatedAt: 2025-05-29T16:58:05.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# Container Env Vars

## Prerequisites

* You've run applications in Docker and have experience building Docker images.

## Service Tokens

Accessing your secrets in production or CI/CD environments requires a  [Service Token](https://docs.doppler.com/docs/service-tokens) to provide read-only access to a specific config. It's exposed to the CLI via the `DOPPLER_TOKEN` environment variable which should be provided by your CI/CD environment, e.g. GitHub Secret.

## Installation

Alternatively, the Doppler CLI can be used to supply environment variables to the container using the `docker run --env-file` flag combined with `doppler secrets download`.

This method requires a bash shell (for [process substitution](https://www.linuxjournal.com/content/shell-process-redirection)) and the Doppler CLI to be installed in the environment running the container. Using the `alpine` image as an example:

```shell
docker run --rm --env-file <(doppler secrets download --no-file --format docker) alpine printenv
```

You should now see your secrets output amongst the other container environment variables.

> 📘 Docker does not support multi-line secrets when using the `--env-file` option so Doppler's `--format docker` flag flattens multi-line secrets by escaping newlines. These can then be converted back to their original form in your application code by replacing the escaped newlines with newlines (replace `\\n` with `\n`).

> 👍 Amazing Work!
>
> Your secrets in Doppler are now ready to be used in your Docker containers.