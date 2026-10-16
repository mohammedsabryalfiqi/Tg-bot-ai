from types import SimpleNamespace

import database
import handlers
import security
from handlers import owner_commands


OWNER_ID = 12345


def _message(text, user_id=OWNER_ID):
    return SimpleNamespace(
        chat=SimpleNamespace(id=user_id),
        from_user=SimpleNamespace(id=user_id),
        text=text,
    )


def test_primary_owner_can_add_list_and_remove_admins(db, stub_bot):
    security.init(stub_bot, OWNER_ID)
    owner_commands.cmd_admin(_message("/admin 501"))
    assert database.is_assistant_admin(501)
    owner_commands.cmd_admin(_message("/admin list"))
    assert "501" in handlers.bot.send_message.call_args.args[1]
    owner_commands.cmd_admin(_message("/admin remove 501"))
    assert not database.is_assistant_admin(501)
    assert database.multi_admin_enabled()


def test_admin_is_limited_to_its_own_tenant(db, stub_bot):
    security.init(stub_bot, OWNER_ID)
    database.add_assistant_admin(501)
    database.add_assistant_admin(502)
    assert security.is_operator_msg(_message("/settings", 501))
    with security.operator_scope(501):
        assert database.tenant_id() == 501
        database.set_setting("business_name", "Only 501")
    with security.operator_scope(502):
        assert database.tenant_id() == 502
        assert database.get_str("business_name") == ""
        database.set_setting("business_name", "Only 502")
    with security.operator_scope(501):
        assert database.get_str("business_name") == "Only 501"


def test_revoked_admin_loses_operator_access_permanently(db, stub_bot):
    security.init(stub_bot, OWNER_ID)
    database.add_assistant_admin(501)
    database.remove_assistant_admin(501)
    assert not security.is_operator_msg(_message("/settings", 501))
    assert database.multi_admin_enabled()
