"""Re-exports for legacy test names.

The shared `invited_employee` fixture used to live here; it now resides in
the project-root `tests/conftest.py` as `employee_in_company_a`. Both
names point at the same factory so historical test code keeps working.
"""

from __future__ import annotations

import pytest

from api.schemas import EmployeeResponse


@pytest.fixture
def invited_employee(employee_in_company_a: EmployeeResponse) -> EmployeeResponse:
    return employee_in_company_a
