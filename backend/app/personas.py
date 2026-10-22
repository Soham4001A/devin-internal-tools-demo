"""Server-controlled DEMO personas. Not real authentication or SSO.

The client sends X-Demo-Persona; the server decides what each persona may do.
"""
PERSONAS = {
    "reviewer": {"id": "reviewer", "name": "Priya Raman", "role": "reviewer",
                 "label": "Priya Raman — Reviewer (demo)", "can_decide": True},
    "viewer": {"id": "viewer", "name": "Marcus Lee", "role": "viewer",
               "label": "Marcus Lee — Viewer (demo)", "can_decide": False},
}
DEFAULT_PERSONA = "viewer"
