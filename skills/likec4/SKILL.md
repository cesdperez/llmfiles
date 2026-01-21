---
name: likec4
description: Architecture-as-code DSL for C4 diagrams. Use when writing LikeC4 files, creating architecture diagrams, defining element specifications, view predicates, dynamic views, or when the user mentions likec4, .likec4 files, or architecture diagrams.
---

# LikeC4 DSL

## Overview

LikeC4 is an architecture-as-code DSL that generates interactive C4 diagrams. Multiple `.likec4` or `.c4` files merge into a single model, enabling modular architecture documentation.

## File Structure

```
architecture/
├── specification.c4      # Element/relationship type definitions
├── model.c4              # System elements and relationships
├── views.c4              # Diagram configurations
├── deployment.c4         # Infrastructure model (optional)
└── likec4.config.ts      # CLI configuration
```

## Core Blocks

Three top-level blocks (order independent, can span multiple files):

```
specification { ... }   // Define element kinds, relationships, tags
model { ... }           // Declare architecture elements
views { ... }           // Configure visualizations
global { ... }          // Shared predicates/styles
```

## Specification (Custom Notation)

```
specification {
  element actor { style { shape person } }
  element system
  element service
  element component
  element database { style { shape storage } }
  element queue { style { shape queue } }
  element external { style { color gray } }

  relationship async
  relationship sync
  relationship uses

  tag deprecated { color red }
  tag critical
  tag v2

  color primary #3B82F6
  color muted #9CA3AF
}
```

**Shapes:** `person`, `browser`, `mobile`, `storage`, `queue`, `cylinder`, `rectangle`

## Model (Elements & Relationships)

```
model {
  actor customer 'Customer'

  system cloud 'Cloud Platform' {
    description 'Main platform'

    service api 'API Gateway' {
      technology 'Node.js'
      #critical
    }

    service orders 'Order Service' {
      component handler 'Order Handler'
      component db 'Orders DB' {
        technology 'PostgreSQL'
      }
      handler -> db 'reads/writes'
    }
  }

  external stripe 'Stripe' {
    description 'Payment processor'
    link https://stripe.com
  }

  // Relationships
  customer -> cloud.api 'places orders'
  cloud.api -> cloud.orders 'routes requests'
  cloud.orders -> stripe 'processes payments' {
    technology 'HTTPS'
    #async
  }
}
```

**Element paths:** Nested elements use dot notation: `cloud.orders.db`

**Relationship kinds:** Use brackets or dot prefix:
```
api -[async]-> queue
api .uses database
```

**Self-reference in nested blocks:** Use `it` or `this`:
```
service orders {
  component api
  component db
  it -> db 'stores'      // orders -> db
  api -> this 'belongs'  // api -> orders
}
```

## Views (Diagrams)

### Basic View

```
views {
  view index {
    title 'System Landscape'
    include *
  }

  view of cloud {
    include *
    exclude external
  }
}
```

### Predicates

**Element predicates:**
```
include *                    // Top-level elements (or children if scoped)
include cloud.*              // Direct children of cloud
include cloud.**             // All descendants
include cloud._              // Children with visible relationships

exclude deprecated
include element.kind = service
exclude element.tag = #deprecated
```

**Relationship predicates:**
```
include customer -> cloud    // Specific relationship
include -> api               // All incoming to api
include api ->               // All outgoing from api
include customer <-> cloud   // Any direction

// Filter relationships
include cloud.* -> * where kind is async
```

**Combining:**
```
include backend, frontend, api
exclude internal.*, legacy
```

### Styling

```
views {
  view landscape {
    include *

    style * { color muted }
    style cloud.* { color primary }
    style external { color gray }
    style element.tag = #deprecated { color red }

    // Relationship styling
    style -> { line dashed }
    style api -> * { color green }
  }
}
```

**With overrides:**
```
include cloud.api with {
  title 'Main API'
  color amber
  navigateTo apiDetailView
}
```

### Groups (Visual Boundaries)

```
view grouped {
  group 'Frontend' {
    color amber
    include webapp, mobile
  }
  group 'Backend' {
    include api, orders, payments
  }
}
```

### Auto-Layout

```
view diagram {
  autoLayout LeftRight 120 110
  // Direction: TopBottom | BottomTop | LeftRight | RightLeft
  // Params: rank distance, node distance
}
```

### Rank Constraints

```
view ranked {
  include *
  rank source { customer }
  rank same { api, gateway }
  rank sink { database }
}
```

### View Inheritance

```
view base {
  include cloud.*
  style * { color primary }
}

view extended extends base {
  include external
  exclude deprecated
}
```

## Dynamic Views (Sequences)

```
views {
  dynamic view checkout {
    title 'Checkout Flow'

    customer -> webapp 'clicks checkout'
    webapp -> api 'POST /checkout'

    parallel {
      api -> inventory 'check stock'
      api -> pricing 'calculate total'
    }

    api -> payments 'process payment'
    payments -> stripe 'charge card'
    api -> customer 'confirmation'
  }
}
```

**Display modes:** Diagram (default) or sequence diagram.

## Global Block (Shared Definitions)

```
global {
  predicateGroup microservices {
    include cloud.* where kind is service
    exclude element.tag = #deprecated
  }

  style warning {
    color amber
    border dashed
  }
}

views {
  view services {
    apply microservices
    apply warning to element.tag = #critical
  }
}
```

## CLI Commands

```bash
# Development server (hot reload)
likec4 start

# Build static site
likec4 build -o ./dist

# Export PNG images
likec4 export png -o ./assets

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

## Pitfalls to Avoid

1. **Forcing hierarchy for layout** - Use view predicates and groups for visual organization, not model nesting

2. **Deep nesting (>3-4 levels)** - Becomes hard to visualize; flatten when possible

3. **Missing descriptions** - Elements without descriptions are unclear in large diagrams

4. **Duplicate element names** - Same-level siblings must have unique names

5. **Predicate order** - Excludes only affect already-included elements; `include *` then `exclude deprecated`

6. **Forgetting `with` for overrides** - Properties in views require `with { }` block

## Quick Reference

| Task | Syntax |
|------|--------|
| Define element kind | `element service { style { shape rectangle } }` |
| Nested element | `service api { component handler }` (path: `api.handler`) |
| Basic relationship | `a -> b 'description'` |
| Typed relationship | `a -[async]-> b` or `a .async b` |
| Include all | `include *` |
| Include children | `include parent.*` |
| Include descendants | `include parent.**` |
| By kind | `include element.kind = service` |
| By tag | `exclude element.tag = #deprecated` |
| Style elements | `style cloud.* { color primary }` |
| Style relationships | `style -> { line dashed }` |
| Visual group | `group 'Name' { include a, b }` |
| Dynamic step | `a -> b 'action'` inside `dynamic view` |
| Parallel steps | `parallel { a -> b; c -> d }` |
| Layout direction | `autoLayout LeftRight` |
| Dev server | `likec4 start` |
| Build | `likec4 build -o ./dist` |
| Export PNG | `likec4 export png -o ./assets` |
