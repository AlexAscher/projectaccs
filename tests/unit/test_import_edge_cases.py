import pytest


@pytest.fixture
def mock_glob():
    from unittest.mock import patch
    with patch('glob.glob') as mock:
        yield mock


# tests/unit/test_import_edge_cases.py
import pytest
import os
import sys
import importlib.util
from unittest.mock import Mock, patch, mock_open


@pytest.fixture
def mock_requests():
    from unittest.mock import patch
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        class RequestsMock:
            get = mock_get
            post = mock_post

        yield RequestsMock


# tests/unit/test_import_edge_cases.py
import os
import sys
import pytest
import importlib.util
from unittest.mock import Mock, patch, mock_open


def load_import_module():
    spec = importlib.util.spec_from_file_location(
        "import_module",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "import", "import.py"))
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["import_module"] = module
    spec.loader.exec_module(module)
    return module


import_module = load_import_module()
import_all = import_module.import_all


def test_import_empty_file(mock_requests, mock_glob, capsys, tmp_path):
    txt_file = tmp_path / "empty.txt"
    txt_file.write_text("")
    mock_glob.return_value = [str(txt_file)]

    with patch("builtins.open", mock_open(read_data="")):
        mock_requests.post.return_value.json.return_value = {"token": "t1"}
        mock_requests.get.return_value.json.return_value = {"items": [{"key": "empty", "id": "p1"}]}
        import_all()
        captured = capsys.readouterr()
        assert "0 из 0 строк" in captured.out


def test_import_malformed_line(mock_requests, mock_glob, capsys, tmp_path):
    txt_file = tmp_path / "bad.txt"
    txt_file.write_text("line with no colons\nvalid:line\n")
    mock_glob.return_value = [str(txt_file)]

    with patch("builtins.open", mock_open(read_data="line with no colons\nvalid:line\n")):
        mock_requests.post.return_value.json.return_value = {"token": "t1"}
        mock_requests.get.side_effect = [
            Mock(json=lambda: {"items": [{"key": "bad", "id": "p1"}]}),
            Mock(json=lambda: {"items": []}),
            Mock(json=lambda: {"items": []}),
        ]
        import_all()
        captured = capsys.readouterr()
        assert "0 из 2 строк успешно" in captured.out