---
source_url: "https://docs.doppler.com/docs/high-availability.md"
content_sha256: 210bc46a68ae89a5cccf1175ee6ed9c639ae71ff913b7ea1a53930e214e92040
content_chars: 5503
---

---
updatedAt: 2025-05-29T16:59:16.000Z
---

Fetch the complete documentation index at: https://docs.doppler.com/llms.txt. Use this file to discover all available pages before exploring further.

# High Availability

Learn how to maintain High Availability with your application while using Doppler.

If you're using Doppler to keep your application's secrets secure and synchronized, what happens if Doppler.com has an outage? Will your application suffer downtime? It definitely can if appropriate precautions aren't taken in advance! While we do our best to ensure Doppler has as little downtime as possible, it's always good to be prepared! This guide will describe several methods for ensuring downtime suffered by Doppler won't impact your application's availability.

## Strategies

There are several ways to help ensure your application remains available during a Doppler outage. Below you'll find these options outlined and explained. Choose whichever option makes the most sense for your deployment!

### Integrations

One of the best ways of avoiding downtime caused by a Doppler outage is by removing Doppler from your application's critical path. You can do that by integrating with the third-party services you're using. This typically involves syncing secrets from Doppler to the service you're using. By doing so, a Doppler outage will only temporarily prevent secret changes from being synced to the third-party platform. Your application would continue having access to any secrets that had previously been synced.

Here are some of the most commonly used:

* [AWS Secrets Manager](https://docs.doppler.com/docs/ekm-aws-secrets-manager)
* [Azure Key Vault](https://docs.doppler.com/docs/azure-key-vault)
* [GCP Secret Manager](https://docs.doppler.com/docs/gcp-secret-manager)

We also have integrations with many other popular platforms, so be sure to look at the available [Integrations](https://docs.doppler.com/docs/integrations).

### Kubernetes Operator

If your applications are deployed in a Kubernetes environment, then you can use our [Kubernetes Operator](https://docs.doppler.com/docs/kubernetes-operator) to sync Doppler secrets to a Kubernetes secret via a DopplerSecret CRD. This will allow you to craft your applications such that they just use native Kubernetes secrets to access any secrets you need. In the event of a Doppler outage, all of your applications will continue being able to access their secrets via the synced Kubernetes secret.

This also has the bonus of protecting you from hitting [platform API rate limits](https://docs.doppler.com/docs/platform-limits). It's fairly common to run into those in large Kubernetes environments during deploy time if your applications are all using `doppler run`. By using the [Kubernetes Operator](https://docs.doppler.com/docs/kubernetes-operator), the number of API requests are limited to those required to keep your secrets synced, so it grows with application count rather than pod count.

### Encrypted Fallback Files

Doppler automatically saves an encrypted fallback snapshot file whenever you use `doppler run`. By default, these are stored at `$HOME/.doppler/fallback` as encrypted JSON files. If the Doppler CLI is unable to reach Doppler.com after a timeout period (typically, 50-60 seconds), it will automatically fall back to using the snapshot file. This will work well automatically in some circumstances, but there are many deployment patterns where this won't work.

#### Docker

Docker is widely used for deploying applications. If you use Docker containers in Kubernetes, we recommend reviewing the [Kubernetes Operator section above](https://docs.doppler.com/docs/high-availability#kubernetes-operator). For all other Docker deployment methods it's important to keep in mind that the default fallback snapshot location may not be persistent. If it isn't and you redeploy your application during an outage, this will mean your application no longer has a fallback file to use when attempting to fetch secrets from Doppler, which can result in downtime.

You can find information on how to ensure your Docker images can be built to maintain High Availability during Doppler outages here:

<https://docs.doppler.com/docs/docker-high-availability>

#### Traditional Deployments

When deploying on bare metal machines or VMs using change management tools like Ansible or Chef, building AWS AMI images, or any other more traditional deployment method – it's important to keep in mind the initial state a new server will come up in. Always consider what will happen if Doppler.com is unavailable when a new server is provisioning.

To ensure High Availability, you'll want to have a job that runs for each of your applications that generates an encrypted snapshot file using `doppler secrets download $APPNAME.encrypted.json` and stores it somewhere secure in your own infrastructure that your deployment process is able to access. Your configuration tooling should then pull that file down locally so that Doppler can use that fallback file in the event Doppler.com is inaccessible. This will ensure that if you ever need to scale your application up or deploy during a Doppler outage, you're able to do so without interruption.

> 🚧
>
> Decrypting the snapshot file is only possible if the `DOPPLER_TOKEN` value at runtime matches the value used at build time or if you specified a passphrase via `DOPPLER_PASSPHRASE` or `--passphrase`. Keep this in mind when generating these fallback snapshot files.