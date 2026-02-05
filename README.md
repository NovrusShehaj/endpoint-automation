# Endpoint Automation & Self-Service Platform

A modular, cross-platform **Python-based endpoint automation tool** designed to scan endpoint health, assess security posture, and provide a foundation for safe, auditable remediation workflows.

This project simulates the kind of tooling used by **Enterprise Endpoint Automation teams** to improve operational stability, security compliance, and self-service capabilities across Windows and macOS environments.

---

## 🎯 Project Goals

The primary goals of this project are to:

* Automate **endpoint health checks** in a safe and non-destructive manner
* Separate **detection (scanning)** from **action (remediation)** following enterprise best practices
* Provide a **self-service CLI** that mirrors real-world IT automation tools
* Lay the groundwork for future integrations with ITSM platforms, CI/CD pipelines, and orchestration engines

This tool is intentionally designed to feel like **production infrastructure**, not a collection of scripts.

---

## 🧠 Design Philosophy

This project follows several core enterprise automation principles:

* **Read-only scans by default** — scanning never modifies system state
* **Explicit separation of concerns** — scanning vs remediation
* **OS-aware behavior** — platform-specific logic where required
* **Auditability** — structured output suitable for logging and reporting
* **Extensibility** — new scanners and remediations can be added easily

---

## 🗂 Project Structure

```
endpoint-automation/
├── endpointctl/
│   ├── cli.py                 # CLI entry point and command routing
│   ├── scanner/               # Read-only health and security checks
│   │   ├── os_info.py          # OS and host metadata
│   │   ├── disk.py             # Disk usage checks
│   │   ├── encryption.py       # Disk encryption detection (BitLocker/FileVault)
│   │   ├── security.py         # Endpoint security baseline checks
│   │   └── __init__.py
│   ├── remediation/            # (Planned) state-changing automation
│   └── __init__.py
├── logs/                       # Runtime logs and audit trail
├── main.py                     # Application entry point
├── README.md
├── venv/
└── tests/                      # (Planned) unit and integration tests
```

---

## ⚙️ Features

### ✅ Endpoint Scanning

The tool currently supports the following **read-only scans**:

* **OS & Host Information**

  * Hostname
  * Operating system
  * OS version
  * Architecture

* **Disk Health**

  * Disk usage percentage
  * Configurable threshold evaluation
  * Status classification (OK / WARNING)

* **Disk Encryption Detection**

  * BitLocker status (Windows)
  * FileVault status (macOS)
  * Graceful handling of unsupported platforms (Linux)

* **Security Baseline Checks**

  * Administrative privilege detection
  * Endpoint protection / XDR process heuristics
  * Baseline security findings

---

## 🖥 CLI Usage

All functionality is exposed through a **self-service command-line interface**.

### Run a Disk Scan

```bash
python3 main.py scan disk
```

### Run an Encryption Scan

```bash
python3 main.py scan encryption
```

### Run a Security Baseline Scan

```bash
python3 main.py scan security
```

### Run a Full Endpoint Scan

```bash
python3 main.py scan all
```

Each command returns structured output suitable for logging, reporting, or downstream automation.

---

## 🔐 Safety & Security Considerations

* **No remediation actions are performed by default**
* Encryption checks are **detect-only**
* Platform-specific commands are wrapped safely
* Errors are captured and returned as structured results

This approach mirrors enterprise endpoint automation standards where scanning is always safe and remediation requires explicit approval.

---

## 🧩 Extensibility

This project is designed to grow.

Planned and easy-to-add enhancements include:

* JSON / CSV export of scan results
* Severity scoring (INFO / WARNING / CRITICAL)
* Scheduled scans (cron / Task Scheduler)
* Remediation workflows with approval gates
* REST API / Web UI (FastAPI)
* ITSM integrations (ServiceNow, Jira)
* CI/CD validation for automation logic

---

## 🧪 Testing Strategy (Planned)

Future testing improvements include:

* Unit tests for scanner modules (pytest)
* Mocking OS-specific commands
* CLI integration tests
* Static analysis and linting

---

## 🛠 Technologies Used

* **Python 3**
* `psutil` — system metrics and process inspection
* `rich` — structured, readable CLI output
* Native OS tooling (BitLocker / FileVault)
* `argparse` — CLI command parsing

---

## 💼 Real-World Relevance

This project reflects the responsibilities of an **Endpoint Automation Engineer**, including:

* Endpoint health monitoring
* Security posture validation
* Automation platform design
* Operational stability and auditability
* Scalable, self-service tooling

It is intentionally aligned with enterprise environments where reliability, safety, and clarity matter more than quick scripts.

---

## 📌 Disclaimer

This project is for **educational and demonstration purposes**. Remediation actions should never be executed in production environments without proper validation, approvals, and safeguards.

---

## 🚀 Next Steps

* Add structured reporting and exports
* Introduce remediation with approval flags
* Build an orchestration layer for workflows
* Package as an installable CLI tool

---

**Author:** Novrus Shehaj

