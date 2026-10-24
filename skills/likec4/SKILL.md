---
name: likec4
description: LikeC4 architecture-as-code DSL for C4 models and views. Use whenever reading or editing a .likec4 or .c4 file, running the likec4 CLI, or drawing architecture, element, or dynamic views.
---

# LikeC4 DSL

LikeC4 is an architecture-as-code DSL that generates interactive C4 diagrams. Multiple `.likec4` or `.c4` files merge into a single model, enabling modular architecture documentation.

## Core Blocks

Four top-level blocks (order independent, can span multiple files):

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

Read `~/llmfiles/skills/likec4/references/views.md` when writing view predicates beyond `include *`, styling, `with` overrides, groups, layout, rank constraints, view inheritance, dynamic views, or the `global` block.

## CLI Commands

```bash
likec4 start                    # Development server (hot reload)
likec4 build -o ./dist          # Build static site
likec4 export png -o ./assets   # Export PNG images
```

Read `~/llmfiles/skills/likec4/references/cli.md` when exporting to Mermaid, PlantUML, D2, or React, running the MCP server, editing `likec4.config.ts`, or laying out a new project's files.

## Pitfalls to Avoid

1. **Forcing hierarchy for layout** - Use view predicates and groups for visual organization, not model nesting
2. **Deep nesting (>3-4 levels)** - Becomes hard to visualize; flatten when possible
3. **Missing descriptions** - Elements without descriptions are unclear in large diagrams
4. **Duplicate element names** - Same-level siblings must have unique names
5. **Predicate order** - Excludes only affect already-included elements; `include *` then `exclude deprecated`
6. **Forgetting `with` for overrides** - Properties in views require `with { }` block
