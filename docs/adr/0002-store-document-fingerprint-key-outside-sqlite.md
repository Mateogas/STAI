---
status: accepted
---

# Store the document-fingerprint key outside SQLite

AISHA will keep its installation-local HMAC-SHA-256 key in a persistent Linux
secret file outside SQLite and the repository, owned by the AISHA service with
mode `0600`. This preserves certificate deduplication across ordinary restarts
without placing the key beside the fingerprints it protects or requiring an
externally managed secret service for the single-installation Proxmox demo.

The key is created atomically only for a fresh installation and rotated during
a Full Demo Reset after Validation Results are cleared. If the key disappears
while Validation Results remain, AISHA must disable certificate checking and
report a safe degraded state instead of silently generating a replacement key.
