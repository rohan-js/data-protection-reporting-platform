SENSITIVE_EVENTS = {
    "DeleteBucket",
    "CreateUser",
    "AttachRolePolicy",
    "AttachUserPolicy",
    "PutUserPolicy",
    "CreatePolicy",
    "AddUserToGroup",
    "PutRolePolicy",
}

PRIVILEGE_ESCALATION_EVENTS = {
    "CreatePolicy",
    "AttachUserPolicy",
    "AttachRolePolicy",
    "PutUserPolicy",
    "AddUserToGroup",
}

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

