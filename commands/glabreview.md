# /glabreview

Review a merge request and provide high-impact improvement suggestions.

## Usage

```
/glabreview <mr-number>
```

## Instructions

1. **Fetch MR information and diff**:
   ```bash
   glab mr view <mr-number> --output json
   glab mr diff <mr-number>
   ```
   Get the MR metadata and changes to understand the full context.

2. **Review changes**: Analyze the diff thoroughly, ultrathink, looking for:
   - Potential bugs or logical errors
   - Security vulnerabilities
   - Performance issues
   - Code quality improvements
   - Simplifications and refactoring opportunities
   - Consistency issues
   - Missing error handling
   - Unnecessary code, imports, or comments

3. **Score each recommendation**: Assign an impact score from 0 to 10:
   - 0-4: Low impact (don't show)
   - 5-6: Medium impact (worth considering)
   - 7-8: High impact (should address)
   - 9-10: Critical impact (must address)

4. **Present recommendations**: Display ONLY recommendations with impact score ≥ 5, including:
   - Title describing the issue
   - Impact score
   - File location and line numbers
   - Clear and concise explanation of the issue
   - Specific code example or recommendation
   - Why this matters (impact justification)

   For each recommendation, also record the anchor needed to post it as a diff comment (see step 6): the **new-side file path and line number** in the MR's latest diff (or `--old-line` when the point is about a removed line). Determine line numbers from the diff hunk headers (`@@ -old,count +new,count @@`) by counting new-side lines (context + added). Findings that don't map to a single line (cross-cutting, or spanning several files) stay as root-level notes.

5. **Wait for user selection**: Ask the user which recommendations they want to post as MR comments. Present options like:
   - "All recommendations"
   - Individual selection by number
   - "None, just show me the review"

6. **Post selected comments**: Post each recommendation as a **diff-anchored comment** tied to the exact file and line, so it shows up inline in the MR's Changes view (requires glab ≥ 1.107; `mr note` is experimental). Do NOT paste the code snippet into the body — the anchor already shows the code in context.

   ```bash
   # New-side line (added/context line in the MR's latest diff)
   glab mr note create <mr-number> --file path/to/file.cs --line 42 -m "**🟡 Impact X/10 — short title.**

   [explanation + recommendation, no code quote]"

   # Removed (old) side, when the point is about a deleted line
   glab mr note create <mr-number> --file path/to/file.cs --old-line 42 -m "..."

   # Multi-line range
   glab mr note create <mr-number> --file path/to/file.cs --line 40:48 -m "..."
   ```

   For a finding that isn't tied to a single line, post a root-level note instead:
   ```bash
   glab mr note create <mr-number> -m "..."
   ```

   Flag rules and gotchas:
   - `--line`/`--old-line` require `--file` and can't be combined with each other.
   - `--file` cannot combine with `--unique`, so diff comments are NOT idempotent. Don't blindly re-run — you'll create duplicates. To re-post, first delete the prior notes via the API:
     ```bash
     glab api "projects/<url-encoded-path>/merge_requests/<mr-number>/notes?per_page=100" --paginate \
       | jq -r '.[] | select(.author.username=="<me>") | .id'
     glab api --method DELETE "projects/<url-encoded-path>/merge_requests/<mr-number>/notes/<note-id>"
     ```
   - glab's success message ("ok noted !create") is cosmetic. Verify placement via the API:
     ```bash
     glab api "projects/<url-encoded-path>/merge_requests/<mr-number>/discussions?per_page=100" --paginate \
       | jq -r '.[].notes[] | "\(.type) \(.position.new_path):\(.position.new_line)"'
     ```

   Format each comment body with:
   - Clear title with impact indicator (e.g., "🔴 Critical", "🟡 Medium") and the impact score
   - Explanation of the issue and why it matters
   - Recommended change (described, not a pasted snippet)

## Example Workflow

```bash
# Step 1: Fetch MR data
glab mr view 624 --output json
glab mr diff 624

# Step 2-4: Analyze and present recommendations
# (Claude performs analysis and shows results)

# Step 5: User selects recommendations to post

# Step 6: Post comments, anchored to the exact diff line
glab mr note create 624 --file Services/UserService.cs --line 45 -m "**🔴 Impact 9/10 — SQL injection.**
User input is concatenated into the query; use a parameterized command instead."

glab mr note create 624 --file Repositories/OrderRepository.cs --line 78 -m "**🟡 Impact 7/10 — N+1 query.**
This loops a query per order; batch it into a single join/IN query."
```

## Example Output Format

```
## Review Results for MR !624

Found 3 high-impact recommendations:

### 1. Security Issue: SQL Injection Vulnerability
**Impact: 9/10** 🔴
**Location:** `Services/UserService.cs:45`

[details here...]

---

### 2. Performance Issue: N+1 Query Problem
**Impact: 7/10** 🟡
**Location:** `Repositories/OrderRepository.cs:78`

[details here...]

---

Which recommendations would you like to post as MR comments?
1. All recommendations
2. Select individually (comma-separated): 1,2,3
3. None (review only)
```

## Notes

- Focus on actionable, specific recommendations
- In the review shown to the user (step 4), code examples are fine; in posted MR comments (step 6), don't paste snippets — the diff anchor already shows the code
- Consider the project's existing patterns and conventions
- Be constructive and helpful in tone
- If no high-impact issues found, report "No recommendations with impact ≥ 5"
