# EchoMind recovery rehearsal

Status: application archive restoration passed; EBS snapshot inspection and the
volume rehearsal require administrator-approved supplemental access. No recovery
access policy or restore volume has been created by this preparation.

## Existing boundaries and access change

The production disk stays attached at `/dev/sdf` and mounted at `/srv/echomind`.
The root disk also remains attached. The application stack, its retained data
volume, the DLM schedule, source snapshots, database and private runtime files are
outside the resources in `restore-drill.yaml`.

An existing IAM administrator may install `restore-access.yaml` as the separate
stack `echomind-restore-access`, using `CAPABILITY_IAM`. Use the same application
name and existing operator, and obtain `ExecutionRoleName` from the role ARN in
the `echomind-provisioning` output. Actual reviewed parameters are generated in
ignored `.publication/restore-access.parameters.json`; inspect them before use.

The two new managed policies:

- Give the existing operator regional snapshot metadata reads, inspection of
  DLM policies carrying this project's tag, and creation/inspection/deletion of
  only `${ApplicationStackName}-restore-drill` with MFA. Creation requires the
  existing fixed project execution role. No updates, imports, IAM writes or
  direct EC2 writes are granted to the operator.
- Let the existing execution role describe source snapshots in this Region.
  Its existing project-scoped volume permissions are reused. No new service
  role, credential, account administrator policy or IAM permission for KMS is added.

The existing operator cannot install these policies itself. Administrative
approval and an authorized administrative session are required. Template
descriptions, source files and this runbook do not constitute that approval.

## Snapshot selection and isolated volume

After access is granted:

1. Read the production stack outputs and live attachments. Record the protected
   root and data VolumeIds. Confirm the instance AZ and that `/dev/sdg` is unused.
2. Inspect the actual DLM policy and its state, project target tag, daily schedule
   and retention. List owned snapshots filtered to the protected data VolumeId.
   Select a **completed, encrypted, owned snapshot** of that disk with the
   expected project backup tags. If none exists, wait for the first scheduled
   backup; do not silently create an extra policy or change its schedule.
3. Verify that the snapshot represents the 20 GiB source disk. Record its ID,
   source VolumeId, creation time, key and tags in the private operation state.
   Create `${ApplicationStackName}-restore-drill` from `restore-drill.yaml`,
   passing that SnapshotId, existing InstanceId and actual AvailabilityZone,
   and the fixed execution RoleARN. This creates only an encrypted gp3 copy and
   an attachment in the unused slot. Stop on failed stabilization.
4. Confirm that the resulting VolumeId is different from both protected IDs,
   has `RestoreDrill` and `Project` tags, uses the expected snapshot and attaches
   only to the intended instance. Verify all this through EC2 and stack outputs.
5. On the host, resolve the new NVMe device by its **VolumeId serial**, not by
   filesystem UUID, `/dev/sdg` alone or guessed NVMe numbering. Verify it is
   unused ext4 and does not resolve to the live/root device. Set the copy's block
   device read-only, then mount it at an empty private directory with
   `ro,noload,nodev,nosuid,noexec`. Do not format it or replay its journal.
6. Verify original files in the copied Docker document-volume directory against
   a pinned, previously validated private archive and the live document
   inventory. Print only counts and pass/fail. Do not start another Docker daemon,
   the backend or recovery worker from the copy; do not inspect secrets or print
   file contents. Do not restore this copy over production during the rehearsal.
7. Unmount the copy and confirm it is no longer mounted. After explicit approval
   for the rehearsal's disposal, delete only the recovery stack. Its disposable
   copy has intentional `DeletionPolicy: Delete`/`UpdateReplacePolicy: Delete`.
   Preserve the protected root/data volumes and source snapshot. Verify the
   temporary volume is gone, the two production attachments remain unchanged,
   originals are valid and public health/HTTPS still pass.

The source snapshot remains the recovery source. A stale snapshot can validly
contain files later removed from production, or omit newer files. A successful
read-only comparison is not a test of service cutover, RTO, Supabase restore or
database/filesystem point-in-time coordination. The database, Auth and external
services need separate recovery procedures.

## Cost and validation

The extra 20 GiB volume is billed for its provisioned storage while it exists,
with the applicable gp3 billing minimum. It can consume account credits. The
template keeps baseline gp3 IOPS/throughput and does not enable Fast Snapshot
Restore or paid initialization. Remove the test copy promptly; account credits
do not make retained resources permanently free. Consult current regional
[EBS pricing](https://aws.amazon.com/ebs/pricing/) before activation.

Local validation uses the existing pinned `echomind-infra-validation:local`
image, with only public files mounted, no credentials and `--network none`:

- cfn-lint validates `restore-access.yaml` and `restore-drill.yaml`.
- `test_restore_drill.py` runs cfn-guard and rejects an unencrypted copy, the live
  device slot, an unintended backup tag, extra compute, IAM writes, loss of MFA
  and deletion of the production stack.
- AWS `ValidateTemplate` checks both templates without installing policies or
  creating a volume. Actual account-aware creation checks remain pending until
  access, snapshot and parameters have been confirmed.

## Application archive check, already independent of EBS access

`deploy/manual/rehearse_document_backup.py` runs inside the existing backend,
with a digest-pinned archive supplied on stdin. It checks the live ready-document
inventory using a read-only database transaction, restores to a newly created
temporary directory, verifies hashes/sizes and removes that directory. It never
drains/restores the live document volume or starts embeddings/recovery. The
archive remains private and unchanged on encrypted data EBS.

This check demonstrates recovery of the archived originals. An archive on the
same disk does not protect against loss of that disk, and this is not an EBS
snapshot restore or a backup of Supabase, Auth, roles or runtime configuration.
