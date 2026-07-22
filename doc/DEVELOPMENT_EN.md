# Plugin development environment

[中文](DEVELOPMENT.md)

This repository uses one long-lived, dedicated development virtual environment. It installs the adjacent WaveBench core checkout and every maintained plugin that has a `pyproject.toml` through standard PEP 660 editable installs. Ordinary Python source changes become visible immediately after restarting the active Python or CLI process; they do not require another installation step.

## First synchronization

The default layout expects sibling `wavebench/` and `wavebench-instrument-plugins/` directories:

```bash
cd wavebench-instrument-plugins
python3 scripts/dev_env.py sync
```

The script creates the ignored repository-local `.venv/`, collects and installs each project's declared build-system requirements, installs `wavebench[dev]` and every maintained plugin as editable distributions, then verifies their real `wavebench.instruments` entry points and registry resolution. `sync` invokes pip and may access configured package indexes to install dependencies on its first run; it is not an offline release gate.

Specify a non-sibling core checkout explicitly:

```bash
python3 scripts/dev_env.py --wavebench-root <wavebench-source> sync
```

## Daily development

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
python3 scripts/dev_env.py check
```

Source edits do not require another `sync`. Synchronize again only when:

- a version, dependency, or entry point changes in `pyproject.toml`;
- a maintained plugin with `pyproject.toml` is added or removed;
- development switches to another WaveBench core checkout; or
- the development virtual environment is deleted or its dependencies need updating.

`check` does not install software, access instruments, or use the network. It compares recorded project metadata, verifies editable core and plugin distributions, requires the instrument entry-point set to match the current maintained-plugin set exactly, and resolves every canonical driver ID through the WaveBench registry. On a later `sync`, the script uses this dedicated environment's own previous state record to uninstall maintained plugins that were removed from the repository. Documentation-only incubation directories without `pyproject.toml` are deliberately skipped.

## Boundary with release acceptance

The editable environment is a development feedback loop, not release acceptance. Before committing or publishing a plugin, continue to use WaveBench `plugin package check`, a real wheel, a disposable virtual environment, and the managed install/remove lifecycle gate. Do not mix editable installs and the WaveBench managed-plugin ledger in one environment; the script refuses to operate when it detects a ledger or unfinished transaction.

Importing a plugin descriptor must still perform no transport I/O. Default tests must not scan ports, connect to instruments, or send SCPI. Hardware tests require separate explicit authorization and sanitized configuration.
