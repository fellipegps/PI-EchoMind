# Local validation only; no credentials, AWS API calls or provisioning.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
RUN python -m pip install --no-cache-dir cfn-lint==1.57.2
ADD --checksum=sha256:8c66efb19c63e6c2bf26b9a41bbcf2f85baa8a937b01d350940194faaf64cf1d https://github.com/aws-cloudformation/cloudformation-guard/releases/download/v3.2.1/cfn-guard-v3-x86_64-linux-latest.tar.gz /tmp/guard.tar.gz
RUN mkdir /tmp/guard \
    && tar -xzf /tmp/guard.tar.gz -C /tmp/guard \
    && find /tmp/guard -type f -name cfn-guard -exec install -m 755 {} /usr/local/bin/cfn-guard \; \
    && cfn-guard --version
WORKDIR /work
USER 10001:10001
