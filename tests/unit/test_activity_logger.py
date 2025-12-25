# tests/unit/test_activity_logger.py
from activity_logger import cache_bot_user_record_id, resolve_bot_user_record_id

def test_cache_and_resolve():
    # Очистка кэша перед тестом
    try:
        from activity_logger import _user_record_cache
        _user_record_cache.clear()
    except Exception:
        pass
    cache_bot_user_record_id("123", "rec_abc")
    from activity_logger import _user_record_cache
    print(f"_user_record_cache after cache: {_user_record_cache}")
    class DummyPB:
        def collection(self, name):
            class Coll:
                def get_first_list_item(self, q):
                    class Rec:
                        id = "rec_abc"
                    return Rec()
            return Coll()
    pb = DummyPB()
    result = resolve_bot_user_record_id(pb, "123")
    print(f"resolve_bot_user_record_id(pb, '123') = {result}")
    assert result == "rec_abc"
    assert resolve_bot_user_record_id(pb, "456") == "rec_abc"