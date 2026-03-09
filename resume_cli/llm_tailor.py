"""
Tailor a resume profile to a job description using an LLM (OpenAI or Bedrock).
Uses a JSON Schema to constrain output so the generated YAML fits the template layout.
"""
import json
import os
from pathlib import Path
from typing import Any

import yaml

# Optional: validate LLM output against schema
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load JSON Schema from file."""
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_limits(limits_path: Path, layout: str) -> dict[str, Any] | None:
    """Load layout limits from a style limits YAML file. Returns the dict for the given layout or None."""
    with open(limits_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return None
    return data.get(layout)


def schema_to_instructions(schema: dict[str, Any], limits: dict[str, Any] | None = None) -> str:
    """Turn the schema (and optional layout limits) into short, clear instructions for the LLM."""
    lines = [
        "Output valid YAML that conforms to this resume profile schema.",
        "Respect these limits exactly (template only shows this many):",
    ]
    if limits:
        if "work" in limits:
            lines.append(f"  - work: at most {limits['work']} items")
        if "workHighlights" in limits:
            lines.append(f"    - each work item: at most {limits['workHighlights']} highlights")
        for key in ("education", "languages", "certificates", "interests", "achievements"):
            if key in limits and limits[key] is not None:
                lines.append(f"  - {key}: at most {limits[key]} items")
    else:
        for key in ("work", "education", "languages", "certificates", "interests", "achievements"):
            prop = schema.get("properties", {}).get(key)
            if prop and "maxItems" in prop:
                lines.append(f"  - {key}: at most {prop['maxItems']} items")
            if key == "work" and prop:
                hi = prop.get("items", {}).get("properties", {}).get("highlights", {})
                if hi.get("maxItems"):
                    lines.append(f"    - each work item: at most {hi['maxItems']} highlights")
    lines.append("")
    lines.append("Required: basics (name, email, label, summary, location with city and countryCode).")
    lines.append("Work items need: name, position, startDate, endDate; highlights as list of strings.")
    lines.append("Achievements need: title, description; optional icon like \\faUserShield.")
    lines.append("Skills: include one group with name 'all' and keywords as a list of skill strings.")
    lines.append("Certificates: name, issuer, and either date (YYYY-MM-DD) or year.")
    return "\n".join(lines)


def tailor_with_openai(
    job_text: str,
    profile_yaml: str,
    schema: dict[str, Any],
    *,
    model: str = "gpt-4o-mini",
    limits: dict[str, Any] | None = None,
) -> str:
    """Call OpenAI API to produce tailored resume YAML. Returns YAML string."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "OpenAI support requires the tailor extra. Install with: uv sync --extra tailor (or pip install openai)"
        ) from None

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    if not client.api_key:
        raise ValueError("Set OPENAI_API_KEY in the environment")

    instructions = schema_to_instructions(schema, limits=limits)
    system = (
        "You are a resume tailor. Given a job description and the candidate's current resume (YAML), "
        "produce a new resume YAML that highlights the most relevant experience, skills, and achievements "
        "for the job. Keep the same person (basics) but select and reorder work, education, skills, "
        "achievements, etc. to match the job. Reword bullets to use the job's language where appropriate. "
        "Output only the YAML document, no markdown code fence or explanation.\n\n"
        f"{instructions}\n\nSchema (for reference):\n{json.dumps(schema, indent=2)}"
    )
    user = (
        "Job description:\n\n"
        f"{job_text}\n\n"
        "Current resume (YAML):\n\n"
        f"{profile_yaml}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    raw = (response.choices[0].message.content or "").strip()
    # Strip markdown code block if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    return raw


def tailor_with_bedrock(
    job_text: str,
    profile_yaml: str,
    schema: dict[str, Any],
    *,
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    region: str | None = None,
    limits: dict[str, Any] | None = None,
) -> str:
    """Call AWS Bedrock to produce tailored resume YAML. Returns YAML string."""
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        raise ImportError("Bedrock support requires: pip install boto3") from None

    region = region or os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)

    instructions = schema_to_instructions(schema, limits=limits)
    system = (
        "You are a resume tailor. Given a job description and the candidate's current resume (YAML), "
        "produce a new resume YAML that highlights the most relevant experience, skills, and achievements "
        "for the job. Keep the same person (basics) but select and reorder work, education, skills, "
        "achievements, etc. to match the job. Reword bullets to use the job's language where appropriate. "
        "Output only the YAML document, no markdown code fence or explanation.\n\n"
        f"{instructions}\n\nSchema (for reference):\n{json.dumps(schema, indent=2)}"
    )
    user = (
        "Job description:\n\n"
        f"{job_text}\n\n"
        "Current resume (YAML):\n\n"
        f"{profile_yaml}"
    )

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "temperature": 0.3,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    raw = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            raw += block.get("text", "")
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    return raw


def enforce_schema_max_items(
    data: dict[str, Any],
    schema: dict[str, Any],
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Truncate arrays to maxItems (from schema or limits) so output fits the template. Modifies copy."""
    data = json.loads(json.dumps(data))  # deep copy
    props = schema.get("properties", {})

    def get_max(key: str, subkey: str | None = None) -> int | None:
        if limits:
            if subkey == "highlights" and key == "work":
                return limits.get("workHighlights")
            if subkey is None and key in limits and limits[key] is not None:
                return limits[key]
        prop = props.get(key) if subkey is None else props.get(key, {}).get("items", {})
        if subkey == "highlights" and key == "work":
            prop = props.get("work", {}).get("items", {}).get("properties", {}).get("highlights", {})
            return prop.get("maxItems")
        return prop.get("maxItems") if isinstance(prop, dict) else None

    for key in ("work", "education", "languages", "certificates", "interests", "achievements", "projects"):
        if key not in data or not isinstance(data[key], list):
            continue
        max_items = get_max(key)
        if max_items is not None and len(data[key]) > max_items:
            data[key] = data[key][:max_items]
        if key == "work" and isinstance(data[key], list):
            hi_max = get_max("work", "highlights")
            if hi_max is not None:
                for item in data[key]:
                    if isinstance(item.get("highlights"), list) and len(item["highlights"]) > hi_max:
                        item["highlights"] = item["highlights"][:hi_max]
    return data


def validate_and_trim(
    yaml_str: str,
    schema: dict[str, Any],
    limits: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Parse YAML, optionally validate with jsonschema, then enforce maxItems (from schema or limits).
    Returns (profile_dict, list of warning messages).
    """
    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a YAML object")

    warnings = []
    if HAS_JSONSCHEMA:
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as e:
            warnings.append(f"Schema validation: {e.message}")
    data = enforce_schema_max_items(data, schema, limits=limits)
    return data, warnings
