Scope: $ARGUMENTS (defaults to "branch" if empty)

If scope is "branch" or empty: analyze only the changes in the current branch compared to the main branch.
If scope is "codebase": analyze the entire codebase.

Ultrathink about:

- Potential improvements
- Potential issues
- Potential simplifications
    - Cleanup unnecessary code
    - Cleanup unnecessary imports
    - Cleanup unnecessary comments

Together with each proposal, include an impact score from 0 to 10. 0 is "no impact" and 10 is "extremely impactful".
Only output proposals with a score of 5 or higher. It's alright to not have any proposals.