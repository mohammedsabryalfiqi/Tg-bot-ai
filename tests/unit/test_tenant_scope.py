"""Isolation primitives for future multi-account assistants."""

import database


def test_settings_are_isolated_by_tenant_and_scope_resets(db):
    database.set_setting("business_name", "Primary")
    with database.tenant_scope(501):
        assert database.get_str("business_name") == ""
        database.set_setting("business_name", "Tenant 501")
        assert database.get_str("business_name") == "Tenant 501"
    with database.tenant_scope(502):
        assert database.get_str("business_name") == ""
        database.set_setting("business_name", "Tenant 502")
    assert database.get_str("business_name") == "Primary"
    with database.tenant_scope(501):
        assert database.get_str("business_name") == "Tenant 501"


def test_admin_membership_crud(db):
    assert database.add_assistant_admin(501) is True
    assert database.add_assistant_admin(501) is False
    assert database.is_assistant_admin(501)
    assert database.list_assistant_admins() == [501]
    assert database.multi_admin_enabled() is True
    assert database.remove_assistant_admin(501) is True
    assert not database.is_assistant_admin(501)
    assert database.list_assistant_admins() == []
    # Once delegation was enabled, removal never re-opens the legacy fallback.
    assert database.multi_admin_enabled() is True
    assert database.add_assistant_admin(501) is True
    assert database.is_assistant_admin(501)


def test_faq_knowledge_and_keys_are_isolated(db):
    database.insert_faq_entry("main", "Main answer")
    database.insert_kb_item("main doc", "text", None)
    database.upsert_api_key("groq", "main-mask", "main-secret")

    with database.tenant_scope(501):
        assert database.list_faq_entries() == []
        database.insert_faq_entry("tenant", "Tenant answer")
        item = database.insert_kb_item("tenant doc", "text", None)
        database.insert_kb_chunks_bulk([(item, 0, "tenant-only content", None)])
        assert database.count_kb_chunks() == 1
        database.upsert_api_key("groq", "tenant-mask", "tenant-secret")
        assert database.get_api_key_row("groq")["encrypted_key_or_plain_local_key"] == "tenant-secret"

    assert [row["keywords"] for row in database.list_faq_entries()] == ["main"]
    assert database.count_kb_chunks() == 0
    assert database.get_api_key_row("groq")["encrypted_key_or_plain_local_key"] == "main-secret"


def test_admin_does_not_inherit_primary_environment_api_key(db, monkeypatch):
    from services import ai_service
    database.add_assistant_admin(501)
    monkeypatch.setenv("OPENAI_API_KEY", "primary-env-secret")
    assert ai_service.resolve_api_key("openai") == "primary-env-secret"
    with database.tenant_scope(501):
        assert ai_service.resolve_api_key("openai") is None
        database.upsert_api_key("openai", "tenant-mask", "tenant-secret")
        assert ai_service.resolve_api_key("openai") == "tenant-secret"


def test_priority_and_do_not_answer_fields_are_added_to_prompt(db):
    from services import prompt_service
    database.set_setting("reply_priorities", "Accuracy first\\nThen concise")
    database.set_setting("never_reply_rules", "Do not quote legal advice")
    prompt = prompt_service.build_system_prompt()
    assert "Accuracy first" in prompt
    assert "Do not quote legal advice" in prompt
