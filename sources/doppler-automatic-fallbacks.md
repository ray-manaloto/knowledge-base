---
source_url: "https://docs.doppler.com/docs/automatic-fallbacks.md"
content_sha256: 010a90fa8d7f043bdb58a402ba11a96e0c42c166ca127210f0ffa35eec4b83b1
content_chars: 5400
---

---
updatedAt: 2025-11-06T22:21:25.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# Secret Fallback Files

When using the `doppler run` command, the CLI automatically creates a fallback file containing an encrypted snapshot of the current secrets in JSON format to Doppler's system configuration directory.

This guide documents how the fallback file works and how you can customize its behavior to optionally create offline secrets access or force the CLI to only use the secrets from a fallback file.

## Overriding the Fallback Path

<Callout icon="🚧" theme="warn">
  If setting the fallback file path, ensure you add this to your `.gitignore`.
</Callout>

You can specify the fallback file location manually. This will tell Doppler where to read and write that fallback file.

```shell
doppler run --fallback=/tmp -- ./your-command-here
```

## Specifying a Passphrase

By default, a secret fallback file can only be decrypted when using the same Doppler token that was used when it was generated. This can cause problems in some situations where you might be pre-seeding a fallback file in a container image prior to deployment. It's unlikely that your CI/CD build system will be using the same Doppler token that your production environment uses.

You can get around this issue by specifying the `--passphrase` flag when creating the fallback file:

```shell
doppler secrets download --passphrase="your-passphrase-here"
```

This will allow any other Doppler token that has access to the project and config to decrypt the fallback file by passing the passphrase in:

```shell
doppler run --fallback=/path/to/doppler.fallback.json --passphrase="your-passphrase-here" -- YOUR_COMMAND_HERE
```

## Disabling Writes

If your application is running in an environment with read-only file permissions, you can instruct the Doppler CLI to only read from an existing fallback file and never write a new one.

```shell
doppler run --fallback-readonly -- ./your-command-here
```

## Only Reading

There may be a case where you would only like to fetch your secrets from the encrypted snapshot instead of Doppler's API. You can instruct the CLI to only read from the fallback file.

```shell
doppler run --fallback-only -- ./your-command-here
```

## FAQ

### I'm getting a `cipher: message authentication failed` message

This is because the passphrase used when attempting to decrypt the secret fallback file didn't match the passphrase used to encrypt it. The default passphrase is constructed using the token, project, and config, so a failure will occur if the passphrase differs at encryption and decryption time, e.g. different `DOPPLER_TOKEN` environment variable supplied in production than was used in in CI build job that downloaded the fallback file.

### Am I able to set the passphrase used for encryption?

Yes, by using the `--passphrase` option when both encrypting (saving) and decrypting (running).

```shell
# Save fallback file during build process
doppler run --fallback doppler.encrypted.json --passphrase "$DOPPLER_PASSPHRASE"

# Access secrets at runtime
doppler run --fallback doppler.encrypted.json --passphrase "$DOPPLER_PASSPHRASE" -- printenv
```

We recommend also storing the passphrase in Doppler and using [secrets referencing](https://docs.doppler.com/docs/secrets#referencing-secrets) to ensure that the passphrase stays in sync between build and deployment environment configs.

### How is the fallback file encrypted?

The CLI uses Go's crypto package with PBKDF2 for key derivation and AES-256-GCM for encryption.

### Does the `--fallback` option prevent the CLI from fetching the latest version of secrets?

The CLI will fetch the latest version of the secrets if the Doppler API is reachable and a valid token is available. You can force the CLI to only use the secrets in the fallback file by using the `--fallback-only` flag.

### Does the CLI eventually require network access after a certain amount of time to continue using the fallback file?

No, the fallback file can be used indefinitely.

### Can I access secrets in formats such as env or YAML when using a fallback file?

Only the default `JSON` format is supported as the fallback file encrypts the secrets in JSON format and this is not configurable.

### Can an expiration time be set to prevent secrets access from a fallback file after a specific duration?

It's achievable but it takes a bit of extra work as the fallback file is not designed with expiry in mind.

If your deployment environment will have access to the Doppler API, you could use an [ephemeral service token](https://docs.doppler.com/docs/service-tokens#ephemeral-service-token) and detect if the service token is still valid before running commands:

```shell
# Test for 'Invalid Auth token' in output
doppler run --fallback doppler.encrypted.json -- printenv 2>&1 | grep  -q 'Invalid Auth token'

if [ $? == 0 ]; then
  echo '[error]: Token invalid. Exiting'
  exit 1
fi

doppler run --fallback doppler.encrypted.json -- your-command
```

Another option is to define your own expiration time and use the Doppler CLI's built-in clean prior to using `doppler run`

```shell
doppler run clean --max-age 24h

# Will fail if fallback file was cleaned up
doppler run --fallback doppler.encrypted.json -- your-command
```