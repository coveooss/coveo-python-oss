import os
import platform
import threading
from queue import Queue
from typing import List

from coveo_testing.markers import UnitTest
from time import sleep

from _pytest.fixtures import SubRequest
from coveo_testing.parametrize import parametrize
from coveo_testing.temporary_resource.unique_id import TestId, unique_test_id

_ = unique_test_id  # mark fixtures are used


@UnitTest
def test_test_id(unique_test_id: TestId, request: SubRequest) -> None:
    this_test_name = "test_test_id"
    assert this_test_name == request.node.name
    assert unique_test_id.friendly_name == this_test_name

    unique_test_id_str = str(unique_test_id)
    assert unique_test_id_str == unique_test_id.id
    if not platform.system().startswith("Darwin"):
        # can anyone explain this behavior...? Why is platform.node() not consistent in github actions on mac?
        # AssertionError:
        # assert 'Mac-1611864959413.local' in 'test_test_id.0128202502.3158.Mac-1611864959413-local.default.0'
        assert platform.node() in unique_test_id_str
    assert str(os.getpid()) in unique_test_id_str


@UnitTest
def test_test_id_sequence(unique_test_id: TestId, request: SubRequest) -> None:
    assert unique_test_id.sequence == 0
    assert TestId(request.node.name).sequence == 1
    assert TestId(request.node.name).sequence == 2


@parametrize("expected_sequence", (0, 1, 2, 3))
@UnitTest
def test_test_id_fixture_within_parametrize(expected_sequence: int, unique_test_id: TestId) -> None:
    assert unique_test_id.sequence == 0
    assert (
        unique_test_id.friendly_name
        == f"test_test_id_fixture_within_parametrize[{expected_sequence}]"
    )


@UnitTest
def test_test_id_threads(request: SubRequest) -> None:
    """test id is thread safe"""
    sequence_count = 10000

    def _thread(queue: Queue) -> None:
        sequence = -1
        while sequence < sequence_count:
            new_sequence = TestId(request.node.name).sequence
            assert new_sequence > sequence  # prevent infinite loops / fail early
            sequence = new_sequence
            if new_sequence < sequence_count:
                queue.put(sequence)

    threads = []
    queue = Queue()
    for _ in range(10):
        thread = threading.Thread(target=_thread, args=(queue,))
        thread.run()
        threads.append(thread)

    while any(t.is_alive() for t in threads):
        sleep(0.1)
    map(lambda t: t.join(), threads)

    sequences: List[int] = []

    while not queue.empty():
        sequences.append(queue.get())
        queue.task_done()
    queue.join()

    assert len(sequences) == len(set(sequences)) == sequence_count, "Duplicates found"
