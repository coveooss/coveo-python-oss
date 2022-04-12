def inner_function() -> str:
    return "Un pangolin ça marche comme M.Burns."


def inner_function_wrapper() -> str:
    return inner_function()


class MockClass:
    class NestedClass:
        class DoubleNestedClass:
            def instance_function(self) -> str:
                return "Sont vraiment cute!"

    def instance_function(self) -> str:
        return "Faudrait tu puisses voir la vidéo sur reddit."

    @classmethod
    def classmethod(cls) -> str:
        return "Tu comprendrais mieux."

    @staticmethod
    def staticmethod() -> str:
        return "L'histoire est pas mal finie!"


class MockClassToRename:
    def instance_function(self) -> str:
        return "À prochaine!"


def inner_mock_class_factory() -> MockClass:
    return MockClass()
