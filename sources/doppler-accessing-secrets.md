---
source_url: "https://docs.doppler.com/docs/accessing-secrets.md"
content_sha256: 004128de15bdd4099a670e346386600e69b09b4edca73a50008a32bbadf1f628
content_chars: 10423
---

---
updatedAt: 2026-07-02T16:20:25.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# Secrets Access Guide

The Doppler CLI is supremely flexible when it comes to accessing your secrets. In this guide, we'll show you the most common usage patterns:

* [Mounting](#mounting)
* [Injection](#injection)
* [Getting Values](#getting-values)
* [Filtering](#filtering)
* [Downloading](#downloading)
* [FAQs](#faqs)

## Mounting

<Callout icon="📘" theme="info">
  ### Mounting on macOS

  Mounting to a directory synced with iCloud Drive will result in an error. Be sure to mount secrets to a local directory.
</Callout>

For applications that read secrets from a file, you can mount an ephemeral .env or JSON file. You can also mount a custom file format using a [secrets template](https://docs.doppler.com/docs/secret-injection-with-templates).

Your secrets are mounted as a Linux named pipe that can be read like a file and is automatically cleaned up when the Doppler process exits, making it the **only** secure method for supplying secrets via the file system.

Simply specify the `--mount` flag and pass the name of the file to mount. The format will automatically be detected for .env and .json files.

To mount an .env file:

```text PHP
doppler run --mount .env -- php artisan serve
```
```shell Node
doppler run --mount .env -- npm start
```

To mount a JSON file:

```shell
doppler run --mount env.json -- npm start
```

Specify the format using `--mount-format` if the extension doesn't automatically map to a known format:

```shell
doppler run --mount app.config --mount-format json -- npm start
```

You can also use a custom template. For example, lets configure Firebase's Cloud Functions emulator using a `.runtimeconfig.json` file:

```shell doppler run
doppler run \
  --mount .runtimeconfig.json \
  --mount-template .runtimeconfig.tmpl -- \
  firebase emulators:start --only functions
```
```text .runtimeconfig.tmpl
{ "doppler": {{tojson .}} }
```

To further increase security, you can restrict the number reads using the `--mount-max-reads` flag. For example, PHP configuration caching that only needs to read the .env file once:

```shell PHP
doppler run --mount .env --mount-max-reads 1 \
	--command="php artisan config:cache && php artisan serve"
```

If using Python and the [dotenv](https://pypi.org/project/python-dotenv/) package, you'll need to slightly adjust your usage of `load_dotenv`:

```python
with open ('.env') as env_file:
	 load_dotenv(stream=env_file)
```

Secrets mounting is perfect for dynamic `kubectl` config files:

```shell doppler run
KUBECONFIG=./kube-config doppler run \
  --mount kube-config \
  --mount-template ./kube-config.tmpl \
  -- kubectl get secrets
```
```text kube-config.tmpl
{{.KUBE_CONFIG}}
```

### Dynamic SSH Key Management

Setting a max number of reads is also great for dynamic SSH private keys, ensuring the private key is deleted once the connection is established:

```shell doppler run
# Nested doppler run so the ssh command can use the SSH_USER and SSH_HOST env vars
# NOTE: The ssh command needs to read the private key twice
doppler run -- \
  doppler run \
    --mount ssh.key \
    --mount-template ssh.key.tmpl \
    --mount-max-reads 2 \ 
    --command 'ssh $SSH_USER@$SSH_HOST -i ssh.key'
```
```text ssh.key.tmpl
{{.SSH_KEY}}
```

## Injection

You can also injects secrets into your application via environment variables, using the `doppler run` command.

```text
doppler run -- npm start
```

### Potential danger when injecting secrets

<Callout icon="🚧" theme="warn">
  ### Caution

  There exists environment variable names that can have unintended consequences when used. In the worst case, they can lead to Remote Code Execution. We advise against using these variables names unless you know what you are doing. The following list is not exhaustive, and is intended to demonstrate the types of variables that significantly alter the behavior of the spawned process.
</Callout>

#### Example Operating System Variables

**Linux**

* `PROMPT_COMMAND`
* `LD_PRELOAD`
* `LD_LIBRARY_PATH`

**Windows**

* `WINDIR`
* `USERPROFILE`

**MacOS**

* `DYLD_INSERT_LIBRARIES`

#### Example Language Interpreter Variables

**Perl**

* `PERL5OPT`

**Python**

* `PERL5OPT`
* `PYTHONWARNINGS`
* `BROWSER`

**PHP**

* `HOSTNAME`
* `PHPRC`

**NodeJS**

* `NODE_VERSION`
* `NODE_OPTIONS`

### Remediation

This danger only exists when injecting secrets as environment variables. We strongly recommend [mounting](#mounting) secrets to an ephemeral file.

## Getting Values

Fetch the plain value of a single secret, e.g. JSON credentials used by a CLI:

```shell
doppler secrets get GCP_SERVICE_ACCOUNT_JSON --plain > gcp_credentials.json
```

You can also use a secret value in a shell command by using the `--command` flag, e.g. performing a `curl` request using Basic Authentication:

```shell
doppler run --command='curl -u $USER:$TOKEN https://example.com'
```

You can download secrets to a file when environment variables aren't sufficient, e.g. supplying a TLS certificate and key to a webserver:

```shell
doppler secrets get TLS_CERT --plain > /etc/tls/cert.pem
doppler secrets get TLS_KEY --plain > /etc/tls/key.pem
```

Get the values of multiple secrets at once in either plain or JSON format:

```shell
# Plain
doppler secrets get DOPPLER_PROJECT DOPPLER_CONFIG --plain

# JSON
doppler secrets get DOPPLER_PROJECT DOPPLER_CONFIG --json
```

You can also get a nice dashboard-style view with the option to exclude the values:

```shell
# Names and values
doppler secrets

# Just names
doppler secrets --only-names

# Names as a JSON array
doppler secrets --only-names --json | jq keys
```

## Filtering

You can use the `doppler secrets download` command in conjunction with tools such as `grep` and `jq` to get a filtered list of secrets.

Filter secrets in env format using grep:

```shell
# Get secrets containing the string "CLOUDWATCH"
doppler secrets download --no-file --format env | grep CLOUDWATCH

# Get secrets starting with "CLOUDWATCH"
doppler secrets download --no-file --format env | grep ^CLOUDWATCH
```

Filter objects in JSON format using `jq`:

```shell
# Get secrets containing the string "CLOUDWATCH"
doppler secrets download --no-file --format json | \
    jq -r '. | to_entries[] | select(.key | contains("CLOUDWATCH)")) | { (.key): (.value)}' | \
    jq -s add

# Get secrets starting with "CLOUDWATCH"
doppler secrets download --no-file --format json | \
    jq -r '. | to_entries[] | select(.key | startswith("CLOUDWATCH")) | { (.key): (.value)}' | \
    jq -s add
```

You can also combine filtering with formatting. For example, create an SSH `authorized_keys` file with the value from secrets with an `SSH_PUB_KEY_` prefix.

```shell
# If secrets in Doppler were
# SSH_PUB_KEY_SERVER_A="ssh-ed25519 AAA..."
# SSH_PUB_KEY_SERVER_B="ssh-ed25519 BBB..."

doppler secrets download --no-file --format env-no-quotes | grep ^SSH_PUB_KEY_ | cut -d"=" -f2 > authorized_keys && chmod 600 authorized_keys
```

## Downloading

<Callout icon="📘" theme="info">
  ###

  We **strongly** recommend against downloading secrets in plain text to the file system. Instead, use Doppler's [mount feature](#mounting) to mount secrets as an ephemeral file.
</Callout>

### Formats

Using the `dopper secrets download` command, you can download your secrets in a variety of formats:

* json (default)
* yaml
* env
* env-no-quotes
* docker
* dotnet-json

For example, to download secrets as a `.env` file:

```shell
# Avoid storing secrets unencrypted whenever possible
doppler secrets download --no-file --format env > .env
```

Custom formats can be achieved by piping secrets in JSON format to  `jq` and transforming the keys and values:

```shell
# Apache environment variable syntax
doppler secrets download --no-file | jq -r '. | to_entries[] | "SetEnv \(.key) \"\(.value)\""' > apache/env-vars.conf
```

Downloading secrets in plain text is only recommended when used with [bash process substitution](https://medium.com/factualopinions/process-substitution-in-bash-739096a2f66d)  to supply secrets to a command expecting a file, but without it ever touching the file system.

Works great with Docker:

```shell
docker run \
   --env-file <(doppler secrets download --no-file --format docker) \
    your/image
```

And Kubernetes:

```shell
kubectl create secret generic \
	doppler-env-vars --from-env-file <(doppler secrets download --no-file --format docker)
```

You can even embed the secrets as part of a larger output, such as syncing Doppler secrets to AWS Lambda using JSON:

```shell
aws lambda update-function-configuration \
    --function-name doppler-test \
    --environment $(echo "{\"Variables\":$(doppler secrets download --no-file)}")
```

## Name Transformers

Name Transformers alter the default UPPER\_SNAKE\_CASE format using the `--name-transformer` option:

```shell doppler run
# ASP.NET Core
doppler run --nane-transformer dotnet-env -- dotnet run

# Terraform
doppler run --name-transformer tf-var -- terraform apply
```

The following naming conventions are supported:

| Type        | Default            | Transform         |
| :---------- | :----------------- | :---------------- |
| camel       | API\_KEY           | apiKey            |
| upper-camel | API\_KEY           | ApiKey            |
| lower-snake | API\_KEY           | api\_key          |
| tf-var      | API\_KEY           | TF\_VAR\_api\_key |
| dotnet-env  | SMTP\_\_USER\_NAME | Smtp\_\_UserName  |
| lower-kebab | API\_KEY           | api-key           |

## FAQs

### How do I export Doppler secrets into the current shell?

A situation may arise when you need to populate a shell with environment variables from Doppler.

<Callout icon="🚧" theme="warn">
  ###

  Exercise caution with this functionality as every process executed in your shell will now have access to your secrets.
</Callout>

You could create a child shell spawned by the Doppler CLI:

```shell bash
doppler run -- sh -c 'bash'
```
```shell zsh
doppler run -- sh -c 'zsh'
```
```shell sh
doppler run -- sh -c 'sh'
```

Or use `doppler secrets download` in conjunction with process substitution to promote Doppler local variables to environment variables.

```shell
set -a
source <(doppler secrets download --no-file --format env)
set +a
```

<br />