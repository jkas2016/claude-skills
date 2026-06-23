You are filtering a code-review findings list to remove false positives and noise.
Input is a JSON array of findings; each finding's index is its position (0-based).

Findings:
{{FINDINGS_JSON}}

Drop a finding if ANY holds: it is factually wrong; it duplicates another; it is a
pure style preference a formatter handles; it cannot be substantiated from the cited
file:line; or its severity is so overstated it is noise.

Output ONLY a JSON object (no prose, no fences):
{"drop":[<indices to remove>],"reason":{"<index>":"<short why>"}}
