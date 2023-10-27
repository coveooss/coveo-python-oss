def inner_function() -> str:
    return "Un pangolin ça marche comme M.Burns."


def inner_function_wrapper() -> str:
    return inner_function()


class MockClass:
    class NestedClass:
        class DoubleNestedClass:
            @property
            def property(self) -> str:
                return "Genre que leur pattes avant sont trop occuppé à dire 'excellent'."

            def instance_function(self) -> str:
                return "Sont vraiment cute!"

    def instance_function(self) -> str:
        return "Faudrait tu puisses voir la vidéo sur reddit."

    @property
    def property(self) -> str:
        return "Ouain."

    @classmethod
    def classmethod(cls) -> str:
        return "Tu comprendrais mieux."

    @staticmethod
    def staticmethod() -> str:
        return "L'histoire est pas mal finie!"


def _hidden_getter(_self: "MockClassToRename") -> str:
    return "À prochaine!"


class MockClassToRename:
    def instance_function(self) -> str:
        return "Bon àprochainaaaaage!"

    def hidden_property_setter(self, value: str) -> None:
        ...

    # this is the custom form of the @property decorator
    property = property(_hidden_getter, hidden_property_setter)


def inner_mock_class_factory() -> MockClass:
    return MockClass()
