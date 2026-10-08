# QC-Studio documentation

QC-Studio is a web-based quality control (QC) application for neuroimaging data. It gives raters
one place to look at raw BIDS data, processed pipeline derivatives, and image quality metrics
(IQMs), assign a structured QC decision with optional notes, and export the result as a
tab-separated table.

## Start here

- **[Overview](overview/overview.md)** — what QC-Studio does, the ideas behind it, and the vocabulary you
  need to read the rest of the documentation.
- **[Installation](overview/installation.md)** — set up a working environment from a clean machine.
- **[Quickstart](overview/quickstart.md)** — run a bundled demo against the sample dataset in a couple of
  commands and take your first QC ratings.

```{toctree}
---
caption: Overview
maxdepth: 2
titlesonly:
hidden:
includehidden:
---
overview/overview
overview/installation
overview/quickstart
```

```{toctree}
---
caption: Guides
maxdepth: 2
titlesonly:
hidden:
includehidden:
---
guides/configuration
guides/ratings
guides/autoplay
```

```{toctree}
---
caption: Development
maxdepth: 2
titlesonly:
hidden:
includehidden:
---
development/architecture
development/dev_plan
```
