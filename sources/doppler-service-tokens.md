---
source_url: "https://docs.doppler.com/docs/service-tokens.md"
content_sha256: c7234b21036367c7696112a28f3cd65325b981b206818c6c94c08bf4c2b97d6e
content_chars: 6464
---

---
updatedAt: 2025-05-29T17:00:11.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# Service Tokens

Provide restricted secrets access to applications in live environments.

A Doppler Service Token provides read-only secrets access to a specific config within a project.

It adheres to the principle of least privilege by ensuring an application only has access to a single config within a project for use in live environments.

> ❗️
>
> Don't use a CLI or Personal Token in live environments as it provides write access with the same permissions as the account it was created by.

## Requirements

* [Doppler CLI](https://docs.doppler.com/docs/cli#installation)
* Access to the config for a project you wish to provide access to

## Creating Service Tokens

### Dashboard

To generate a Service Token using the dashboard

1. Go to the Project and select a Config
2. Click the **Access** tab.
3. Click on **Generate**.
4. Provide a name for the token and optionally provide the token with write access or assign an expiration.
5. Click on **Generate Service Token**
6. Copy the Service Token as it is only shown once.

<Image align="center" width="80% " src="https://files.readme.io/003b3000b45dd30cd5c2087ca66f17af76312feb58d0519692421c648d7b5572-CleanShot_2024-11-20_at_09.35.45.gif" />

### CLI

You can also generate a Service Token using the Doppler CLI:

```shell
# Select the project and config
doppler setup

# Create the Service Token
doppler configs tokens create token-name --plain
```

You can also create the Service Token in a single command by providing the project and config as arguments:

```shell
doppler configs tokens create --project your-project --config your-config token-name --plain
```

## Using Service Tokens with the CLI

There are three ways to configure the Doppler CLI to use the Service Token.

### Option 1: Persisted Service Token

This is the best option for Virtual Machines as it restricts which directory secrets can be fetched from and no additional configuration is required once registered (e.g. will persist across machine restarts).

```shell
# Prevent configure command being leaked in bash history
export HISTIGNORE='doppler*'

# Scope to location of application directory
echo 'dp.st.prd.xxxx' | doppler configure set token --scope /usr/src/app

# Supply secrets to your application
cd /usr/src/app
doppler run -- your-command-here
```

If refreshing the Service Token, the `doppler configure set token` will need to be run again with the new Service Token value.

### Option 2: The `DOPPLER_TOKEN` environment variable

This method best suits environments where a Doppler integration sync isn't possible (e.g [Render](https://docs.doppler.com/docs/render)) or when secrets access to multiple configs are required (e.g. [CircleCI](https://docs.doppler.com/docs/circleci#option-2-service-tokens) jobs for staging and production).

The other common use case is when running your application via the shell or shell script:

```shell
# Prevent command with Service Token being recorded in bash history
export HISTIGNORE='export DOPPLER_TOKEN*'

export DOPPLER_TOKEN='dp.st.prd.xxxx'
doppler run -- your-command-here
```

With [Docker](https://docs.doppler.com/docs/dockerfile):

```shell
# Prevent command with Service Token being recorded in bash history
export HISTIGNORE='docker*'

docker container run -e DOPPLER_TOKEN='dp.st.prd.xxxx' your-app
```

[Docker Compose](https://docs.doppler.com/docs/enclave-docker-compose#option-1-dockerfile):

```shell
# Prevent command with Service Token being recorded in bash history
export HISTIGNORE='export DOPPLER_TOKEN*'

export DOPPLER_TOKEN='dp.st.prd.xxxx'
docker-compose up
```

Or [Kubernetes](https://docs.doppler.com/docs/kubernetes-doppler-cli-in-docker):

```shell
# Prevent command with Service Token being recorded in bash history
export HISTIGNORE='kubectl create secret*'

# Create Kubernetes secret containing the Service Token
kubectl create secret generic doppler-token --from-literal=DOPPLER_TOKEN="dp.st.prd.xxxx"
```

Inject `SERVICE_TOKEN` into your Kubernetes deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
...
    spec:
      containers:
        - name: your-app 
          envFrom:
            - secretRef:
                name: doppler-token
```

### Option 3: The `--token` argument

It's also possible to use the `--token` option for `doppler run`:

```shell
# Prevent command with Service Token being recorded in bash history
export HISTIGNORE='doppler run*'

doppler run --token='dp.st.prd.xxxx' -- your-command-here
```

## Ephemeral Service Tokens

An ephemeral Service Token can be created by setting an expiration time. Once the duration is reached, the token is automatically deleted.

<Image align="center" width="40% " src="https://files.readme.io/75ea1e2bc2cceb4e363682a300fbc170fb0aacb1048d39caabca9cb3178e5c54-Service_Tokens.png" />

You can also create an ephemeral Service Token via the CLI using the `--max-age` option:

```shell
export DOPPLER_TOKEN=$(doppler configs tokens create ephemeral-token --max-age 1m --plain)
```

Here's an example of using an ephemeral Service Token to provide temporary secrets access to a Docker container.

<HTMLBlock>{`
<div class="video-embed">
   <iframe src="https://player.vimeo.com/video/651849552" frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>
 </div>
`}</HTMLBlock>

## Revoking Service Tokens

Revoking a Service Token is non-reversible and immediately prevents secrets access.

### Dashboard

Revoking a Service Token from the Dashboard is performed from the **Access** tab for the Config by clicking **Revoke**.

<Image align="center" width="80% " src="https://files.readme.io/dcc64e5c34f4694892c50b6a0b17dd62188099582b787d70207b917e52814337-Service_Tokens-1.png" />

### CLI

Revoking a Service Token from the CLI can be done by executing the following command:

```shell
doppler configs tokens revoke -p PROJECT -c CONFIG dp.st.dev.fHhinxK...
```

> 🚧 Revoking a token and the secrets fallback file
>
> If a token is revoked, this will prevent access to the latest version of the secrets, but the CLI will continue to provide the last accessed version of the secrets (if it has previously been able to access the secrets) due to the [encrypted fallback file](https://docs.doppler.com/docs/enclave-automatic-fallbacks) being stored on disk.