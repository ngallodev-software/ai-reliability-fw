# demo/fixtures.py

# HAPPY PATH INPUT
HAPPY_PATH_PRD = {
    "title": "User Authentication Service",
    "version": "1.0",
    "requirements": [
        {
            "id": "REQ-001",
            "description": "Users must be able to log in using email and password.",
            "acceptance_criteria": [
                "Given valid credentials, user receives JWT within 500ms.",
                "Given invalid credentials, user receives 401 with no credential details."
            ]
        }
    ],
    "named_entities": ["JWT", "OAuth2"],
    "citations": ["RFC 7519", "OWASP Authentication Cheat Sheet"]
}

# FAILURE PATH INPUT — injected defects:
# 1. Empty acceptance_criteria (triggers MISSING_REQUIRED_FIELD)
# 2. Ungrounded named entity "ZephyrAuth" (triggers HALLUCINATION_SIGNAL)
FAILURE_PATH_PRD = {
    "title": "User Authentication Service",
    "version": "1.0",
    "requirements": [
        {
            "id": "REQ-001",
            "description": "Users must be able to log in using ZephyrAuth protocol.",
            "acceptance_criteria": []  # Empty trigger
        }
    ],
    "named_entities": ["ZephyrAuth"],
    "citations": []  # No citations to ground ZephyrAuth
}

# The Expected Output Schema for the LLM
PRD_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "missing_components": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["summary", "risk_level", "missing_components"]
}
