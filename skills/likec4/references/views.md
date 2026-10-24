# LikeC4 Views Reference

Full view syntax: predicates, styling, overrides, groups, layout, inheritance, dynamic views, and the global block.

## Predicates

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

## Styling

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

## Groups (Visual Boundaries)

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

## Auto-Layout

```
view diagram {
  autoLayout LeftRight 120 110
  // Direction: TopBottom | BottomTop | LeftRight | RightLeft
  // Params: rank distance, node distance
}
```

## Rank Constraints

```
view ranked {
  include *
  rank source { customer }
  rank same { api, gateway }
  rank sink { database }
}
```

## View Inheritance

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

Single-line parallel block: `parallel { a -> b; c -> d }`

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
