# assets/

Static media — images, diagrams, logos, screenshots.

## Purpose

Binary and visual files that support the documentation and, later, the web interface. Kept out of `docs/` so that directory stays readable as prose.

## Expected contents

| Kind | Use |
|---|---|
| Architecture diagrams | Referenced from `docs/` |
| Screenshots | README and documentation |
| Logos and brand marks | The eventual web interface |
| Social preview image | GitHub repository card |

## Conventions

- **Prefer text-based formats.** SVG for diagrams, since it diffs meaningfully in version control and scales cleanly. Reach for PNG only when SVG cannot do the job.
- **Descriptive filenames.** `system-architecture-phase1.svg`, not `diagram2.png`.
- **Compress before committing.** Git keeps every version of a binary forever; an uncompressed screenshot is permanent weight in the repository.
- **Nothing generated.** If a build step can produce it, it should not be committed.

## Not for

- Media the assistant reads at runtime — that belongs in `knowledge/`.
- Large binaries. If something exceeds a few megabytes, host it elsewhere and link to it.
