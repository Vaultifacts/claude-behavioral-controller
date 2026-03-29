---
description: Node.js project conventions
paths: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.mjs", "package.json", "tsconfig.json"]
---

- Package manager: npm (not yarn or bun unless project specifies)
- Always check `package.json` scripts before running commands
- Use `npx` only for project-local tools (e.g. `npx tsc` picks up local tsconfig)
- Next.js: `npm run dev` for local, `npm run build` for production check
- **Windows spawn() rule**: ALWAYS use `shell: true` when spawning `.cmd`/`.bat` files. Omitting causes `Error: spawn EINVAL`.
