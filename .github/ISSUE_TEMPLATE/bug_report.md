---
name: Bug Report
about: Report a bug or issue with EverMemOS
title: '[BUG] '
labels: ['bug']
assignees: ''
---

# Bug Report

Thank you for taking the time to report a bug! Please fill out the information below to help us understand and fix the issue.

---

## Bug Description

**What happened?**
A clear and concise description of the bug.

---

## Steps to Reproduce

Please provide detailed steps to reproduce the issue:

1.
2.
3.

---

## Expected Behavior

What did you expect to happen?

---

## Actual Behavior

What actually happened? Include any error messages or unexpected output.

---

## Environment

**System Information:**
- **OS**: (e.g., macOS 13.0, Ubuntu 22.04, Windows 11 WSL2)
- **Python Version**: (run `python --version`)
- **EverMemOS Version**: (e.g., v1.1.0, or commit hash)
- **Installation Method**: (Docker / Manual)

**Dependencies:**
- **Docker Version**: (if using Docker, run `docker --version`)
- **MongoDB Version**:
- **Elasticsearch Version**:
- **Milvus Version**:
- **Redis Version**:

---

## Configuration

**Relevant configuration from `.env` (remove sensitive values):**
```
LLM_API_BASE=...
VECTORIZE_API_BASE=...
# etc.
```

---

## Logs

**Error logs or stack traces:**
```
Paste relevant logs here
```

**Terminal output:**
```
Paste command output here
```

---

## Screenshots

If applicable, add screenshots to help explain the problem.

---

## Additional Context

Any other information that might be helpful:
- Does this happen consistently or intermittently?
- Did this work before? If so, what changed?
- Have you tried any workarounds?

---

## Checklist

Before submitting, please check:

- [ ] I have searched existing issues to avoid duplicates
- [ ] I have provided all requested information
- [ ] I have removed any sensitive information (API keys, passwords, etc.)
- [ ] I can reproduce this issue consistently

---

**Note**: For security vulnerabilities, please do NOT create a public issue. Instead, refer to our [Security Policy](../SECURITY.md).
