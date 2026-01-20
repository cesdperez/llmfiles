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

5. **Wait for user selection**: Ask the user which recommendations they want to post as MR comments. Present options like:
   - "All recommendations"
   - Individual selection by number
   - "None, just show me the review"

6. **Post selected comments**: For each selected recommendation, use:
   ```bash
   glab mr note <mr-number> --message "## Title Here

**Impact: X/10** 🔴

**Location:** \`path/to/file.cs:line\`

[Full formatted content here...]" --unique
   ```

   The `--unique` flag prevents duplicate comments if the command is run multiple times.

   Format each comment with:
   - Clear title with impact indicator (e.g., "🔴 Critical", "🟡 Medium")
   - File location reference
   - Current code snippet
   - Recommended change (if applicable)
   - Explanation of impact

## Example Workflow

```bash
# Step 1: Fetch MR data
glab mr view 624 --output json
glab mr diff 624

# Step 2-4: Analyze and present recommendations
# (Claude performs analysis and shows results)

# Step 5: User selects recommendations to post

# Step 6: Post comments
glab mr note 624 --message "## Security Issue: SQL Injection Vulnerability
**Impact: 9/10** 🔴
**Location:** \`Services/UserService.cs:45\`
..." --unique

glab mr note 624 --message "## Performance Issue: N+1 Query
**Impact: 7/10** 🟡
**Location:** \`Repositories/OrderRepository.cs:78\`
..." --unique
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
- Prefer showing code examples over abstract descriptions
- Consider the project's existing patterns and conventions
- Be constructive and helpful in tone
- If no high-impact issues found, report "No recommendations with impact ≥ 5"
