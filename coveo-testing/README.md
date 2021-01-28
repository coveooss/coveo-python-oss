# coveo-testing

A set of test/pytest helpers to facilitate common routines.


Content in a nutshell:

- Reusable pytest markers (UnitTest, IntegrationTest)
- TemporaryResource fixture class with unique ID generation
- Multiline logging assertions with includes, excludes, levels and comprehensive assertion output
- Refactorable "unittest.mock.patch('this.module')" module references
- Human-readable (but still customizable) display for parametrized tests


This project is used as the test base for all other prrojects in this repository.
Therefore, it cannot depend on any of them.

More complex use cases may be implemented in the `coveo-testing-extras` project. That's also where you can depend on projects that depend on `coveo-testing`. 
