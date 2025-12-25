# tests/unit/test_import.py
import os
import sys
import pytest
from unittest.mock import Mock, patch, mock_open
import importlib.util

def load_import_module():
    spec = importlib.util.spec_from_file_location(
        "import_module",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "import", "import.py"))
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["import_module"] = module
    spec.loader.exec_module(module)
    return module

# Загружаем модуль
import_module = load_import_module()
login_user = import_module.login_user
fetch_records = import_module.fetch_records
record_exists = import_module.record_exists
import_all = import_module.import_all
POCKETBASE_URL = import_module.POCKETBASE_URL
USER_EMAIL = import_module.USER_EMAIL
USER_PASSWORD = import_module.USER_PASSWORD
IMPORT_DIR = import_module.IMPORT_DIR

@pytest.fixture
def mock_requests():
    with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
        class RequestsMock:
            get = mock_get
            post = mock_post
        yield RequestsMock

@pytest.fixture
def mock_glob():
    with patch('glob.glob') as mock:
        yield mock

def test_login_user_success(mock_requests):
    mock_requests.post.return_value.json.return_value = {"token": "fake_token"}
    token = login_user("test@example.com", "pass123")
    assert token == "fake_token"

def test_record_exists_true(mock_requests):
    mock_requests.get.return_value.json.return_value = {"items": [{"id": "acc1"}]}
    exists = record_exists("login:pass:email", "prod123", "token")
    assert exists is True

def test_record_exists_false(mock_requests):
    mock_requests.get.return_value.json.return_value = {"items": []}
    exists = record_exists("new_data", "prod456", "token")
    assert exists is False

def test_import_all_no_txt_files(mock_requests, mock_glob, capsys):
    mock_glob.return_value = []
    import_all()
    captured = capsys.readouterr()
    assert "Нет .txt файлов" in captured.out

def test_import_all_product_not_found(mock_requests, mock_glob, capsys):
    mock_glob.return_value = ["import/import_txt/unknown.txt"]
    mock_requests.post.return_value.json.return_value = {"token": "t1"}
    mock_requests.get.return_value.json.return_value = {"items": [{"key": "known", "id": "p1"}]}
    with patch("builtins.open", mock_open(read_data="acc1\n")):
        import_all()
    captured = capsys.readouterr()
    assert "продукт `unknown` не найден" in captured.out

def test_import_all_success(mock_requests, mock_glob, capsys):
    mock_glob.return_value = ["import/import_txt/test.txt"]
    with patch("builtins.open", mock_open(read_data="acc1\nacc2\n")):
        mock_requests.post.return_value.json.return_value = {"token": "t1"}
        mock_requests.get.side_effect = [
            Mock(json=lambda: {"items": [{"key": "test", "id": "p1"}]}),
            Mock(json=lambda: {"items": []}),
            Mock(json=lambda: {"items": []}),
            Mock(status_code=200),
            Mock(status_code=200),
        ]
        import_all()
        captured = capsys.readouterr()
        assert "успешно" in captured.out

def test_import_all_skip_duplicates(mock_requests, mock_glob, capsys):
    mock_glob.return_value = ["import/import_txt/test.txt"]
    with patch("builtins.open", mock_open(read_data="acc1\n")):
        mock_requests.post.return_value.json.return_value = {"token": "t1"}
        mock_requests.get.side_effect = [
            Mock(json=lambda: {"items": [{"key": "test", "id": "p1"}]}),
            Mock(json=lambda: {"items": [{"id": "old"}]}),
        ]
        import_all()
        captured = capsys.readouterr()
        assert "уже в базе" in captured.out