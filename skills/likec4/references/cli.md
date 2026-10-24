# LikeC4 CLI and Configuration Reference

## Project Layout

```
architecture/
├── specification.c4      # Element/relationship type definitions
├── model.c4              # System elements and relationships
├── views.c4              # Diagram configurations
├── deployment.c4         # Infrastructure model (optional)
└── likec4.config.ts      # CLI configuration
```

## CLI Commands

```bash
# Export to other formats
likec4 codegen mermaid
likec4 codegen plantuml
likec4 codegen d2

# Generate React components
likec4 codegen react --outfile ./components

# MCP server for AI integration
likec4 mcp
likec4 mcp --http -p 3335
```

## Configuration (likec4.config.ts)

```typescript
import { defineConfig } from 'likec4/config';

export default defineConfig({
  name: 'My Architecture',
  title: 'System Architecture',
  exclude: ['node_modules/**'],
});
```
