from resume_gate import Verdict, validate_resume


def base_checkpoint():
    return {
        "checkpoint_id": "cp-1",
        "created_at": "2026-10-01T10:00:00Z",
        "policy_version": "policy-v1",
        "runtime": {"agent_version": "1.0.0", "state_schema": "3", "model": "model-a"},
        "tools": {"refund": {"version": "2", "permission": "refund:write"}},
        "authorities": [
            {
                "id": "approval-381",
                "scope": "refund:order-77",
                "status": "active",
                "expires_at": "2026-10-05T00:00:00Z",
                "policy_version": "policy-v1",
            }
        ],
        "dependencies": [
            {
                "id": "pricing-schema",
                "version": "v4",
                "observed_at": "2026-10-01T10:00:00Z",
                "max_age_seconds": 86400,
            }
        ],
        "side_effects": [
            {
                "id": "refund-77",
                "tool": "refund",
                "status": "committed",
                "idempotency_key": "refund:77",
                "receipt": "rcpt-77",
            }
        ],
    }


def base_current():
    return {
        "now": "2026-10-01T12:00:00Z",
        "policy_version": "policy-v1",
        "runtime": {"agent_version": "1.0.0", "state_schema": "3", "model": "model-a"},
        "tools": {"refund": {"version": "2", "permission": "refund:write"}},
        "authorities": [
            {
                "id": "approval-381",
                "scope": "refund:order-77",
                "status": "active",
                "expires_at": "2026-10-05T00:00:00Z",
                "policy_version": "policy-v1",
            }
        ],
        "dependencies": [
            {"id": "pricing-schema", "version": "v4", "observed_at": "2026-10-01T11:30:00Z"}
        ],
    }


def test_safe_when_manifest_still_matches():
    result = validate_resume(base_checkpoint(), base_current())
    assert result.verdict is Verdict.SAFE
    assert result.issues == ()


def test_blocks_revoked_approval():
    current = base_current()
    current["authorities"][0]["status"] = "revoked"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.BLOCK
    assert "AUTHORITY_NOT_ACTIVE" in {issue.code for issue in result.issues}


def test_blocks_expired_approval():
    current = base_current()
    current["now"] = "2026-10-06T00:00:00Z"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.BLOCK
    assert "AUTHORITY_EXPIRED" in {issue.code for issue in result.issues}


def test_blocks_removed_tool():
    current = base_current()
    current["tools"] = {}
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.BLOCK
    assert "TOOL_REMOVED" in {issue.code for issue in result.issues}


def test_blocks_permission_change():
    current = base_current()
    current["tools"]["refund"]["permission"] = "refund:read"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.BLOCK
    assert "TOOL_PERMISSION_CHANGED" in {issue.code for issue in result.issues}


def test_schema_change_requires_migration():
    current = base_current()
    current["runtime"]["state_schema"] = "4"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.MIGRATE


def test_runtime_change_requires_revalidation():
    current = base_current()
    current["runtime"]["agent_version"] = "1.1.0"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.REVALIDATE


def test_dependency_change_requires_revalidation():
    current = base_current()
    current["dependencies"][0]["version"] = "v5"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.REVALIDATE
    assert "DEPENDENCY_CHANGED" in {issue.code for issue in result.issues}


def test_stale_dependency_requires_revalidation():
    current = base_current()
    current["now"] = "2026-10-03T12:00:00Z"
    current["dependencies"][0]["observed_at"] = "2026-10-01T11:30:00Z"
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.REVALIDATE
    assert "DEPENDENCY_STALE" in {issue.code for issue in result.issues}


def test_uncertain_non_idempotent_side_effect_blocks():
    checkpoint = base_checkpoint()
    checkpoint["side_effects"] = [{"id": "charge-1", "tool": "charge", "status": "unknown"}]
    result = validate_resume(checkpoint, base_current())
    assert result.verdict is Verdict.BLOCK
    assert "NON_IDEMPOTENT_SIDE_EFFECT_UNCERTAIN" in {issue.code for issue in result.issues}


def test_uncertain_idempotent_side_effect_requires_revalidation():
    checkpoint = base_checkpoint()
    checkpoint["side_effects"] = [
        {"id": "charge-1", "tool": "charge", "status": "unknown", "idempotency_key": "charge:1"}
    ]
    result = validate_resume(checkpoint, base_current())
    assert result.verdict is Verdict.REVALIDATE
    assert "SIDE_EFFECT_UNCERTAIN" in {issue.code for issue in result.issues}


def test_block_outranks_migrate_and_revalidate():
    current = base_current()
    current["runtime"]["state_schema"] = "4"
    current["runtime"]["agent_version"] = "2.0.0"
    current["tools"] = {}
    result = validate_resume(base_checkpoint(), current)
    assert result.verdict is Verdict.BLOCK
