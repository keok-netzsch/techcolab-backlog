"""Smoke tests for every page in views/.

After the monolith refactor, each page is a views/<name>.py with a render()
function. ruff's F821 catches undefined names statically, but not runtime errors
(bad attribute access, wrong call signatures, template/format bugs). These tests
render each page through Streamlit's AppTest and assert it raises no exception.

They run against whatever vault is configured: with an empty/absent vault the
pages must still render their "no data" branches without crashing (which is
exactly the kind of regression worth catching).
"""

import pytest
from streamlit.testing.v1 import AppTest

VIEWS = [
    "backlog",
    "todo_list",
    "dashboard",
    "weekly_brief",
    "tutorial",
    "documentation",
    "team",
    "claude_pro",
    "english_coach",
    "faq",
    "settings",
]


@pytest.mark.parametrize("modname", VIEWS)
def test_view_renders_without_exception(modname):
    # from_string (not from_function): runs a real script that imports the module
    # with its full namespace (module-level globals, helpers, imports) and calls
    # render(). from_function would re-exec only the function body in isolation.
    at = AppTest.from_string(f"from views.{modname} import render\nrender()")
    at.run(timeout=60)
    assert not at.exception, f"views.{modname}.render() raised: {at.exception}"
