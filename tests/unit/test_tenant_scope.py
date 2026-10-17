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


def test_admin_inherits_primary_selected_model_but_not_content(db):
    database.set_setting("ai_provider", "groq")
    database.set_setting("ai_model_by_provider", '{"groq":"openai/gpt-oss-120b"}')
    database.set_setting("business_name", "Primary Business")
    with database.tenant_scope(501):
        assert database.get_str("ai_provider") == "groq"
        assert database.get_str("ai_model_by_provider") == '{"groq":"openai/gpt-oss-120b"}'
        assert database.get_str("business_name") == ""


def test_admin_uses_shared_environment_key_without_copying_it(db, monkeypatch):
    from services import ai_service
    database.add_assistant_admin(501)
    monkeypatch.setenv("OPENAI_API_KEY", "primary-env-secret")
    with database.tenant_scope(501):
        assert ai_service.resolve_api_key("openai") == "primary-env-secret"
        assert ai_service.key_source("openai") == "shared"
        assert database.get_api_key_row("openai") is None
        assert "secret" not in ai_service.masked_active_key("openai")
        assert ai_service.status_lines()
        # An administrator must not be able to disconnect everyone's env key.
        ai_service.disconnect_api_key("openai")
        assert ai_service.resolve_api_key("openai") == "primary-env-secret"


def test_shared_database_key_rotates_immediately_and_keeps_content_private(db):
    from services import ai_service
    database.set_setting("ai_provider", "openai")
    ai_service.store_api_key("central-first", "openai")
    with database.tenant_scope(501):
        ai_service.store_api_key("local-key", "openai", persist_env=True)
        database.set_setting("custom_instructions", "Private to 501")
        assert ai_service.resolve_api_key() == "central-first"
        assert ai_service.is_ready()
    ai_service.store_api_key("central-rotated", "openai")
    with database.tenant_scope(501):
        assert ai_service.resolve_api_key() == "central-rotated"
        assert database.get_api_key_row("openai")["encrypted_key_or_plain_local_key"] == "plain:local-key"
    with database.tenant_scope(502):
        assert ai_service.resolve_api_key() == "central-rotated"
        assert database.get_str("custom_instructions") == ""
    ai_service.disconnect_api_key("openai")
    with database.tenant_scope(501):
        assert ai_service.resolve_api_key() == "local-key"


def test_priority_and_do_not_answer_fields_are_added_to_prompt(db):
    from services import prompt_service
    database.set_setting("reply_priorities", "Accuracy first\\nThen concise")
    database.set_setting("never_reply_rules", "Do not quote legal advice")
    prompt = prompt_service.build_system_prompt()
    assert "Accuracy first" in prompt
    assert "Do not quote legal advice" in prompt
