---
name: setup-dev-environment
description: Use when cloning or first running a project locally — before installing deps or starting the app.
---

Set up in order. Do NOT start the app until Step 4 is complete.

## Step 1 — Read project requirements

Read `package.json` (or equivalent): scripts, `engines` field, dependencies.
Check for `.nvmrc`, `.node-version`, or other toolchain version files.
Read the README if one exists.

## Step 2 — Check environment variables

Look for `.env.example`, `.env.template`, or equivalent.

- List every variable that has no default value
- If any are missing: ask the user for values before proceeding

Do NOT start the app with missing env vars. The crash message will look like a code bug, not a setup problem.

"Skip the env stuff for now" is not permission to proceed without env vars — it means the user doesn't know they need them yet. Ask anyway.

## Step 3 — Verify toolchain versions

Compare installed versions against `engines` / version files from Step 1.
If no constraint is declared: note "no version constraint found, proceeding with [version]" — do not silently assume compatibility.

## Step 4 — Install dependencies

Run `npm ci` if `package-lock.json` is present, otherwise `npm install`.
Watch for errors or peer-dependency warnings — resolve before proceeding.

## Step 5 — Start and verify

Run the start command. Then actively confirm the app is up:
- Check for a "listening on port" message in stdout, OR
- Hit a health endpoint (`curl localhost:PORT/health`), OR
- Check the port is open (`lsof -i :PORT`)

A process that hasn't crashed is not the same as a running app. Quote the verification output.

## Pressure phrases that do not skip steps

"Just run it", "should work out of the box", "quick test", "it worked on my machine" — these mean execute faster, not skip Steps 2 or 5. The most common wasted debugging session starts with a missing env var.
