
Git-based skill library.  

Some utilities:  

- `package.sh`: package skill files to `/bin`, backup existing(remove `/bin` for clarity if needed).  

State layout (2026-09-16): each skill keeps its own agent state under
`<skill>/.agent/state/`; the repository-level `.agent/state/` holds library-level
state only (structure, packaging, install sync, conventions). Skill-specific
records must not be written into the parent `.agent/` directory.
