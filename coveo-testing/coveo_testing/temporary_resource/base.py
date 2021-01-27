from abc import abstractmethod
from contextlib import contextmanager
import logging
from typing import Generator, TypeVar


log = logging.getLogger(__name__)

# Type that represent the type of self for classes that derives from TmpResource.
T = TypeVar("T", bound="TemporaryResource")


class TemporaryResource:
    """ Base class used for creating temporary unit test objects """

    _disposed: bool = False

    @abstractmethod
    def create_resource(self) -> None:
        """ Creates the object. """
        assert not self._disposed

    @abstractmethod
    def delete_resource(self) -> None:
        """ Delete the temporary object(s) """
        assert not self._disposed
        self._disposed = True

    @contextmanager
    def auto_delete(self: T) -> Generator[T, None, None]:
        """ Provides a contextmanager that deletes the resource on exit. """
        assert not self._disposed
        yield self
        self.delete_resource()
