# First installation on EC2

This path bootstraps the first application release without enabling the GitHub
pipeline or granting the instance additional AWS permissions. Subsequent CI/CD
releases remain governed by `deploy/pipeline`.

1. Commit reviewed installation tools and application changes. Run
   `package_source.py --output .publication/source.tar.gz` from the checkout.
   It packages only allowlisted regular files from **HEAD**, never `.env`,
   documents, local backups, working-tree changes or Git metadata.
2. Send the public source archive through authenticated SSM Run Command in
   bounded chunks. Verify its SHA256 before extracting into a new root-owned
   `/srv/echomind/releases/<commit>` directory (`700`). Reject links and path
   traversal. Inside that protected root, use `755` for public source directories
   and `644` for source files: Docker COPY preserves these modes and the non-root
   application needs read/traverse access inside its image.
   Build using `bash deploy/manual/build_first_release.sh <commit>` from there.
   Build output stays in restricted host logs; images use the full source commit.
3. Generate a fresh RSA 3072-bit one-day recipient certificate and private key
   **on EC2** in `/etc/echomind/transfer`, root-owned directory `700`, files `600`.
   Only the public certificate leaves the host. This is a temporary encryption
   recipient, separate from the API's public HTTPS certificate.
4. Confirm the actual Supabase **session pooler** hostname in its Connect panel.
   Run `prepare_envelope.py` using the backend virtual environment, the public
   recipient certificate and installed OpenSSL. It reads the existing local
   credentials in process, validates production defaults and writes only CMS
   ciphertext into ignored `.publication/`. It does not fetch AWS secrets.
5. Send only ciphertext through SSM. Pass its SHA256 in the authenticated command
   and run `install_envelope.py --sha256 <digest>` on EC2. It checks file ownership,
   permissions, size and digest, decrypts in memory and delegates atomic runtime
   installation to `configure_runtime.py`. It refuses to overwrite an existing
   runtime. It removes the transfer key, certificate and ciphertext on exit.
6. Install `/etc/echomind/deploy.env` with real image tags, domain and certificate
   contact, root `600`. Validate Compose with `config --quiet`. Check the database
   from the production image before starting the public HTTPS services. No
   migrations or reindexing run automatically. Record actual checks separately.

Do not print decrypted configuration, Docker environment inspections or raw
application logs into chat/SSM outputs. The CMS ciphertext's integrity depends
on the SHA256 supplied by the authenticated control channel. This is an
operator-controlled first installation, not a general artifact distribution
service. It does not change IAM or create new AWS resources.

Offline checks: `deploy/manual/test_private_transfer.py` uses synthetic values
only and an OpenSSL binary selected by `TEST_OPENSSL`. Real Linux permissions,
database connectivity and public TLS must also be verified on the actual host.

External verification (no credentials or user records):

```sh
python deploy/manual/verify_public.py \
  --domain echomind-api.duckdns.org \
  --origin https://echomind-front.vercel.app
```

Checks trusted TLS/hostname, health, HTTP redirect, HSTS, exact-origin CORS and
denial of anonymous access to `/auth/me`. It does not exercise login, model
responses, uploads, certificate renewal or application capacity. The first
installation was recorded in `docs/first-publication-verification.json`;
the frontend follow-up is in `docs/frontend-publication-verification.json`.
CI/CD activation remains separate.

## Backend-only updates of an existing manual installation

`update_release.py` reuses the transaction in `deploy/pipeline/rollout.py` without
activating the pipeline or creating AWS resources. Package and transfer committed
source as above, retain its authenticated archive at
`/srv/echomind/incoming/<revision>.tar.gz`, verify/extract into a fresh release,
and build the candidate backend before invoking:

```sh
python3 deploy/manual/update_release.py --revision <full-commit> --sha256 <archive-sha256>
```

Run from that verified source directory as root. Compose and proxy inputs must
match the existing installation. The updater locks deployments, checks readiness,
drains document writes and saves a private document recovery archive on encrypted
data EBS, then recreates only the backend with its persistent volumes. It verifies
database readiness, public HTTPS and exact container image/proxy identities before
resuming writes and committing state. It updates only the public image setting;
the existing backend runtime secrets are handed to Docker without reading values.
There are no automatic migrations, reindexing or volume/image deletions.

If startup or verification fails, the shared transaction restores the previous
backend. Interrupted operations retain `manual-rollout/pending.json`; inspect and
reconcile it before retrying. Successful operations retain `previous.json` and
`previous-installation.json` in that private directory, plus the previous image and
source. Post-transaction metadata failures also require reconciliation rather than
blindly rerunning. The local archive is recovery assistance, not an off-host backup.

Offline checks: `python deploy/manual/test_update_release.py` and the 20 pipeline
transaction/security tests (run the latter on Linux).

## Read-only checks and a missing original

`check_application_host.py` runs on the EC2 host with Docker inspection access.
It emits container health, limits, cgroup memory and allowlisted operational
event fields. It never emits Docker environment values or raw application logs.
Its memory counters cover the lifetime of the current container, not a load test.

`check_document_originals.py` runs inside the backend as its ordinary UID, using
its existing runtime configuration. It checks ready-document sizes and digests
without printing content, names, identities or credentials. `--absent-id` may
check that a specific approved disposable fixture has been removed. It returns
nonzero for missing/invalid originals, queued jobs, maintenance or a remaining
fixture. Counts are a point-in-time observation; concurrent writes may change
them. Neither checker changes database records or application configuration.

`restore_document_original.py` repairs one missing original for an existing
ready document. Run it inside the backend as its ordinary UID. Feed a version-1
JSON envelope containing `document_id`, `sha256` and `original_b64` through a
private pipe after the CMS transfer/digest verification described above.
Never place plaintext/base64 user files in SSM command arguments, tool output,
Git or shell history. Use a fresh recipient key and remove it and ciphertext
with an exit trap after the transfer.

The default is validation only; `--apply` explicitly installs the file. The tool
matches the current database size/digest/status under the admission and row
locks, refuses pending jobs and unsafe paths, creates an atomic no-clobber file
with mode `600`, and verifies it again. It does not mutate the database, create
job markers or reindex chunks. An existing valid original is left in place; an
invalid existing original aborts the operation. Use only for the specific file
authorized by its owner; this is not a volume or database backup restoration.

## Controlled capacity observation

`observe_capacity.py` runs on the existing EC2 host without importing the model,
reading runtime secrets or creating another application container. It samples
host memory/swap/disks/CPU and the existing backend/proxy cgroups every two
seconds. Its JSON output contains counters only and is replaced atomically.
`--duration` is bounded to 30 minutes; `--stop-file` finishes observation early.
Use a private host directory for the output and a fresh stop-marker path.

The `load_guard_ok` flag rejects additional load when sampled memory reaches
90% of a container limit, host available memory drops below 192 MiB, a container
is replaced/restarted/unhealthy, or new OOM/limit events occur. The observer is
read-only: it does not cancel uploads, kill processes or stop an active workload.
Check its current report between separately bounded phases. Keep cold-model
benchmarks in an isolated local container; a second model process on the 2 GiB
production host would measure a different workload and compete with the API.

`../measure_public_chat.py` sends one batch of 1, 2 or 4 public synthetic requests
to the existing EchoMind API, without credentials, cookies or session extraction.
Use only a test account's public slug and previously approved synthetic content.
The default uses the same question in every request so concurrency comparisons
do not change question wording. `--question-index` selects another fixed control;
`--mixed-questions` tests wording separately. Do not treat a mixed batch as a
controlled concurrency comparison.

The verifier requires HTTP 200 and the expected synthetic identifier, normalizing
Unicode hyphens from generated prose. It never prints response text. The measured
duration includes client network/TLS, database/retrieval and the LLM; isolated
batches do not establish sustained throughput, percentile latency or capacity
after CPU credits run out. Account for synthetic interaction/metric records left
in the test account, and obtain the required confirmation before permanent file
cleanup. Run `python deploy/test_capacity_tools.py` for counter and output checks.
