"""Safe mock tools.

Every tool in this package:
  * reads from controlled fixtures under `data/fixtures/`
  * performs defensive input validation
  * never touches a real external system
  * increments an in-process execution counter for tests
"""