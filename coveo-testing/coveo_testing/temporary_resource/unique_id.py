from datetime import datetime
import itertools
import os
import platform
import re
import threading
from typing import Dict, ClassVar, Iterator

import pytest
from _pytest.fixtures import SubRequest
from typing_extensions import Final


class TestId:
    """
    Generates a "unique-enough" test id made up from human-readable components.

    - Threaded test executors will increment sequence number.
    - Multiprocess test executors would use different pids.
    - Jenkins executors provide different executor labels.
    """

    DELIMITER: Final[str] = "."
    HOST: Final[str] = platform.node()
    PID: Final[int] = os.getpid()
    TIMESTAMP: Final[datetime] = datetime.now()
    # this exists on jenkins. using it ensures that running parallel tests on shared resources (like docker sockets)
    # cannot create the same id.
    EXECUTOR: Final[str] = os.environ.get("EXECUTOR_NUMBER", "default")

    # each friendly name keeps a count.
    _sequence_count: ClassVar[Dict[str, Iterator[int]]] = {}
    _threading_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, friendly_name: str) -> None:
        self.friendly_name: str = friendly_name
        with self._threading_lock:
            self.sequence = next(self._sequence_count.setdefault(friendly_name, itertools.count()))
        parts = tuple(
            map(
                self._isolate_and_sanitize_id_part,
                (
                    self.friendly_name,
                    self.TIMESTAMP.strftime("%m%d%H%M%S"),
                    str(self.PID),
                    self.HOST,
                    self.EXECUTOR,
                    str(self.sequence),
                ),
            )
        )
        assert self.DELIMITER not in "".join(parts)
        self.id = self.DELIMITER.join(parts)

    @classmethod
    def _isolate_and_sanitize_id_part(cls, string: str) -> str:
        """ Return a new string that doesn't contain invalid characters or the name tokenization delimiter """
        replacement = "-"
        assert (
            replacement != cls.DELIMITER
        ), "Use a replacement character that's different from the delimiter."
        # remove delimiter from pattern so that it disappears from the string
        replace_pattern = r"[^a-zA-Z0-9_.-]".replace(cls.DELIMITER, "")
        return re.sub(replace_pattern, replacement, string)

    def __str__(self) -> str:
        return self.id


@pytest.fixture
def unique_test_id(request: SubRequest) -> TestId:
    """Provide a TestId object scoped to your test method

    Parametrized methods will trigger one TestId per parameter. The TestId's friendly name will include the "ids"
    that pytest generates for each parametrized test.

    e.g.:
        @parametrize('value', (3, True))
        def test_params(unique_test_id: TestId, value: int) -> None:
            assert unique_test_id.friendly_name == f"test_params[{value}]"  # test_params[3], test_params[True], etc
            assert unique_test_id.sequence == 0

    e.g.:
        @parametrize('value', (3, True), ids=('three', 'bool'))
        def test_params(unique_test_id: TestId, value: Any) -> None:
            ...  # test_params[three], test_params[bool], etc
    """
    return TestId(request.node.name)
