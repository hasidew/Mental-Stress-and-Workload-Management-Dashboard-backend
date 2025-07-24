from fastapi import FastAPI
from main import app   # Import your FastAPI app

import json
print("Generating OpenAPI schema...")

# Get the OpenAPI schema
openapi_schema = app.openapi()

# Save it to a JSON file
with open("openapi_schema.json", "w") as f:
    json.dump(openapi_schema, f, indent=2)

print("✅ OpenAPI schema saved to openapi_schema.json")
