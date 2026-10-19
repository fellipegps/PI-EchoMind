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
