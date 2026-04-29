---
description: Rules for creating pytest-based integration tests that validate workbench Docker/Podman images using testcontainers
globs: "tests/test_*.py,tests/containers/**/*.py"
alwaysApply: false
---

# Python Integration Tests Rules

Integration tests in the notebooks repository validate workbench images (JupyterLab, RStudio, Code Server) by running them in containers and testing their behavior.

## When to Write Integration Tests

Write integration tests when you need to:
- Validate a workbench image starts correctly
- Test image entrypoints and startup behavior
- Verify installed packages, extensions, or libraries
- Test network configurations (IPv4/IPv6)
- Validate environment variables and configuration
- Test Dockerfile changes
- Verify image manifests (ImageStream YAML files)
- Test Python dependency lockfiles (pyproject.toml/pylock.toml)

## Framework and Tools

| Tool | Purpose |
|------|---------|
| **pytest** | Test framework |
| **testcontainers** | Docker/Podman container management |
| **pytest-subtests** | Parametrized test variations |
| **allure-pytest** | Test reporting and issue tracking |
| **docker-py** | Docker API client |
| **requests** | HTTP client for testing web endpoints |

## Test File Structure

### File Naming and Location

**Pattern**: `test_*.py` or `*_test.py`

**Locations**:
- `tests/test_main.py` - Main repository-wide tests (Dockerfiles, manifests, pyprojects)
- `tests/containers/workbenches/workbench_image_test.py` - Base workbench image tests
- `tests/containers/workbenches/jupyterlab/jupyterlab_test.py` - JupyterLab-specific tests
- `tests/containers/workbenches/rstudio/rstudio_test.py` - RStudio-specific tests

### Test Organization

```python
from __future__ import annotations

import logging
import pytest
import allure
from tests.containers import conftest, docker_utils
from tests.containers.workbenches.workbench_image_test import WorkbenchContainer

class TestWorkbenchImage:
    """Tests for workbench images in this repository."""
    
    @allure.issue("RHOAIENG-12345")
    @allure.description("Test description here")
    def test_feature_name(self, workbench_image: str) -> None:
        container = WorkbenchContainer(image=workbench_image, user=1000, group_add=[0])
        try:
            container.start()
            # Test logic here
        finally:
            docker_utils.NotebookContainer(container).stop(timeout=0)
```

## Integration Test Patterns

### 1. Basic Container Startup Test

```python
@allure.issue("RHOAIENG-XXXXX")
@allure.description("Verify the workbench image starts correctly")
def test_image_entrypoint_starts(self, workbench_image: str) -> None:
    container = WorkbenchContainer(
        image=workbench_image,
        user=1000,
        group_add=[0]
    )
    try:
        container.start()
        container._connect()  # Verify HTTP endpoint is accessible
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Use `WorkbenchContainer` class for workbench images
- Set `user=1000` and `group_add=[0]` for proper permissions
- Always call `container.start()` before testing
- Use `container._connect()` to verify HTTP readiness
- Always stop containers in `finally` block with `timeout=0`

### 2. Parametrized Tests

```python
@pytest.mark.parametrize(
    "sysctls",
    [
        {},
        {"net.ipv6.conf.all.disable_ipv6": "1"},  # Test with IPv6 disabled
    ],
)
def test_with_different_configs(
    self, 
    subtests: pytest_subtests.SubTests,
    workbench_image: str,
    sysctls
) -> None:
    container = WorkbenchContainer(
        image=workbench_image,
        user=1000,
        group_add=[0],
        sysctls=sysctls
    )
    try:
        container.start()
        with subtests.test("Attempting to connect to the workbench..."):
            container._connect()
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Use `@pytest.mark.parametrize` for multiple configurations
- Use `subtests` for granular failure reporting
- Each parameter combination runs as a separate test

### 3. Container Execution Tests

```python
@allure.issue("RHOAIENG-XXXXX")
@allure.description("Check that extension is installed and enabled")
def test_extension_installed(self, jupyterlab_image: conftest.Image) -> None:
    container = WorkbenchContainer(
        image=jupyterlab_image.name,
        user=4321,
        group_add=[0]
    )
    try:
        container.start(wait_for_readiness=False)
        exit_code, output = container.exec(["jupyter", "labextension", "list"])
        result_output = output.decode(errors="replace")
        assert exit_code == 0, f"`jupyter labextension list` failed:\n{result_output}"
        assert "extension-name" in result_output, (
            "Extension not found in output:\n" + result_output
        )
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Use `container.exec()` to run commands inside the container
- Returns tuple of `(exit_code, output_bytes)`
- Decode output with `errors="replace"` for robustness
- Assert exit code before checking output content
- Provide detailed error messages with output

### 4. Environment Variable Configuration

```python
def test_with_custom_notebook_args(self, jupyterlab_image: conftest.Image) -> None:
    container = WorkbenchContainer(
        image=jupyterlab_image.name,
        user=4321,
        group_add=[0]
    )
    container.with_env(
        "NOTEBOOK_ARGS",
        "\n".join([
            "--ServerApp.port=8888",
            "--ServerApp.token=''",
            "--ServerApp.password=''",
            "--ServerApp.base_url=/notebook/opendatahub/jovyan",
            "--ServerApp.quit_button=False",
        ]),
    )
    try:
        container.start(wait_for_readiness=False)
        container._connect(base_url="/notebook/opendatahub/jovyan")
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Use `container.with_env()` to set environment variables
- Multi-line values use `"\n".join()` pattern
- Custom base URLs require `wait_for_readiness=False` + manual `_connect()`

### 5. Network Testing (IPv6)

```python
def test_ipv6_only(
    self,
    subtests: pytest_subtests.SubTests,
    workbench_image: str,
    test_frame
) -> None:
    """Test that workbench image is accessible via IPv6."""
    network = testcontainers.core.network.Network(
        docker_network_kw={
            "ipam": docker.types.IPAMConfig(
                pool_configs=[
                    docker.types.IPAMPool(subnet="fd00::/64"),
                ]
            )
        }
    )
    test_frame.append(network)  # Register for cleanup
    
    container = WorkbenchContainer(image=workbench_image)
    container.with_network(network)
    try:
        client = testcontainers.core.docker_client.DockerClient()
        rootless: bool = client.client.info()["Rootless"]
        container.start(wait_for_readiness=rootless)
        
        if rootless:
            container._connect()
        else:
            # Rootful containers: connect via IPv6 address
            container.get_wrapped_container().reload()
            ipv6_address = container.get_wrapped_container().attrs[
                "NetworkSettings"]["Networks"][network.name]["GlobalIPv6Address"
            ]
            # ... connect to ipv6_address ...
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Create custom networks for IPv6-only testing
- Register network with `test_frame` for automatic cleanup
- Check if running rootless vs rootful Podman/Docker
- Different connection strategies for rootless vs rootful

### 6. HTTP Request Validation

```python
@allure.issue("RHOAIENG-11156")
@allure.description("Check that the HTML contains expected elements")
def test_html_content(self, jupyterlab_image: conftest.Image) -> None:
    container = WorkbenchContainer(
        image=jupyterlab_image.name,
        user=4321,
        group_add=[0]
    )
    try:
        container.start(wait_for_readiness=False)
        container._connect(base_url="/notebook/opendatahub/jovyan")
        
        host_ip = container.get_container_host_ip()
        host_port = container.get_exposed_port(container.port)
        response = requests.get(f"http://{host_ip}:{host_port}/notebook/opendatahub/jovyan")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert 'class="pf-v6-c-spinner"' in response.text, (
            "Expected PatternFly spinner in initial page HTML"
        )
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Use `container.get_container_host_ip()` and `container.get_exposed_port()`
- Make HTTP requests with `requests` library
- Validate status code, headers, and response content
- Provide specific assertion messages

### 7. Conditional Test Skipping

```python
def test_architecture_specific_feature(self, jupyterlab_image: conftest.Image) -> None:
    container = WorkbenchContainer(
        image=jupyterlab_image.name,
        user=4321,
        group_add=[0]
    )
    container.start(wait_for_readiness=False)
    try:
        exit_code, arch_output = container.exec(["uname", "-m"])
        arch = arch_output.decode().strip()
        if exit_code == 0 and arch in ("s390x", "ppc64le"):
            pytest.skip("Feature not supported on s390x/ppc64le architecture")
        
        # Test logic for supported architectures
    finally:
        docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Key Points**:
- Use `pytest.skip()` for environment-specific skips
- Check architecture, OS, or other runtime conditions
- Skip early to avoid unnecessary test execution

## Fixtures

### Common Fixtures (from conftest.py)

| Fixture | Type | Purpose |
|---------|------|---------|
| `workbench_image` | `str` | Workbench image name from pytest parameter |
| `jupyterlab_image` | `conftest.Image` | JupyterLab image object |
| `subtests` | `pytest_subtests.SubTests` | Subtest support for parametrized tests |
| `test_frame` | `list` | Resource cleanup frame for networks/containers |

### Using Image Fixtures

```python
def test_with_image_fixture(self, jupyterlab_image: conftest.Image) -> None:
    # Access image name
    image_name = jupyterlab_image.name
    
    # Access image metadata
    # jupyterlab_image has: .name, .path, .metadata, etc.
    
    container = WorkbenchContainer(image=image_name, ...)
```

## Repository-Wide Test Patterns

### Testing Dockerfiles

```python
def test_dockerfiles_pattern():
    """Test that Dockerfiles don't match problematic patterns."""
    pattern = re.compile(r"^[^#]*subscription-manager.[^#]*register")
    
    for file in PROJECT_ROOT.glob("**/Dockerfile*"):
        if file.is_dir():
            continue
        with open(file, "r") as f:
            for line_no, line in enumerate(f, start=1):
                assert not pattern.match(line), (
                    f"Problematic pattern found in {file}:{line_no}"
                )
```

### Testing Manifests

```python
@pytest.mark.parametrize(
    "manifests_directory",
    [manifests.MANIFESTS_ODH_DIR, manifests.MANIFESTS_RHOAI_DIR]
)
def test_manifest_structure(subtests, manifests_directory: pathlib.Path):
    for manifest_file in manifests_directory.glob("*.yaml"):
        with subtests.test(manifest=manifest_file):
            manifest = yaml.safe_load(manifest_file.read_text())
            assert "kind" in manifest
            assert "metadata" in manifest
```

### Testing Pyprojects

```python
def test_pyproject_toml(subtests):
    for file in PROJECT_ROOT.glob("**/pyproject.toml"):
        with subtests.test(msg="checking pyproject.toml", pyproject=file):
            pyproject = tomllib.loads(file.read_text())
            assert "project" in pyproject
            assert "requires-python" in pyproject["project"]
            assert "dependencies" in pyproject["project"]
```

## Best Practices Summary

### DO ✅
- Always use `try/finally` for container cleanup
- Set `user=1000, group_add=[0]` for workbench containers
- Use `timeout=0` when stopping containers in cleanup
- Add `@allure.issue()` for Jira issue tracking
- Add `@allure.description()` for test documentation
- Use subtests for parametrized test variations
- Decode command output with `errors="replace"`
- Provide detailed assertion messages with context
- Use `container.exec()` for in-container commands
- Check exit codes before validating output

### DON'T ❌
- Don't leave containers running after tests
- Don't hardcode image names (use fixtures)
- Don't use `sleep()` for timing (use wait strategies)
- Don't test without proper error messages
- Don't ignore exit codes from `container.exec()`
- Don't commit tests without issue references
- Don't create containers without cleanup blocks
- Don't use `wait_for_readiness=True` with custom base URLs

## Implementation Checklist

### Before writing tests
- [ ] Identify which workbench image to test
- [ ] Determine if test needs network configuration
- [ ] Check if existing fixtures can be reused
- [ ] Create Jira issue and note the ID

### During implementation
- [ ] Create test class with descriptive name
- [ ] Add `@allure.issue()` decorator
- [ ] Add `@allure.description()` decorator
- [ ] Create `WorkbenchContainer` with proper user/group
- [ ] Wrap container operations in `try/finally`
- [ ] Add cleanup with `timeout=0`
- [ ] Use subtests for parametrized variations
- [ ] Add meaningful assertion messages

### After implementation
- [ ] Run tests locally and verify they pass
- [ ] Check that containers are properly cleaned up
- [ ] Verify tests work with different image variants
- [ ] Add test to appropriate test class
- [ ] Update test documentation if needed
- [ ] Commit with descriptive message
