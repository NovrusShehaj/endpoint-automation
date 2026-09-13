"""Test doubles shared across the suite."""

from __future__ import annotations


class FakeToolResult:
    """Stand-in for :class:`endpointctl.process.ToolResult`."""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int | None = 0,
        failure: str | None = None,
        error: str | None = None,
    ) -> None:
        self.argv = ("fake",)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.failure = failure
        self.error = error

    @property
    def ok(self) -> bool:
        return self.failure is None and self.returncode == 0


class FakeProcess:
    """Stand-in for a psutil process yielded by ``process_iter(["name"])``."""

    def __init__(self, name: str | None = None, raises: BaseException | None = None) -> None:
        self._name = name
        self._raises = raises

    @property
    def info(self) -> dict[str, str | None]:
        if self._raises is not None:
            raise self._raises
        return {"name": self._name}
