# LICENSE decision — databubble-python

**Status:** blocking issue for PyPI publish. `pyproject.toml` already
declares `license = {text = "MIT"}`, but no `LICENSE` file exists in the repo
— PyPI and most tooling expect the actual license text to be present, not
just the metadata field.

This is the one remaining decision only you can make — pick an option below,
or a different license entirely, and the file can be dropped in directly.

## Option A — Keep MIT (matches current metadata, no changes needed elsewhere)

- Permissive: anyone can use, modify, sell, and sublicense the SDK, including
  in closed-source products, with no obligation to share changes back.
- Standard choice for a thin API client library — the value you're
  protecting is the DataBubble *service* (the API itself, gated by paid
  keys), not the client code that talks to it. Most comparable API SDKs
  (Stripe, OpenAI, Anthropic's own Python SDK) use MIT or Apache-2.0 for
  exactly this reason: an unrestrictive client encourages adoption, and
  doesn't compete with the thing you actually monetize.
- Lowest friction for external contributors and for anyone wrapping the SDK
  in their own tooling.

## Option B — Apache 2.0

- Same permissiveness as MIT, plus an explicit patent grant and a NOTICE-file
  mechanism. Marginally more paperwork, mostly relevant if patent risk is a
  real concern (unlikely for a thin HTTP client).
- Would require updating `pyproject.toml`'s `license` field and re-verifying
  nothing else assumes MIT.

## Option C — Something copyleft (GPL/AGPL family)

- Not recommended here. Copyleft is normally chosen to force downstream
  contributions back or to prevent commercial re-bundling of the *code
  itself* — neither applies well to a client library whose entire purpose is
  to be embedded in other people's applications to call your paid API. It
  would likely suppress adoption without protecting anything you actually
  care about (the API, the statistical engine, and the knowledge base are
  all in the other two repos, under no obligation to be open at all).

## Recommendation

Option A (keep MIT, add the `LICENSE` file) is the lowest-friction, most
conventional choice for this repo's actual role, and requires no other
changes since the metadata is already set. Recommended unless there's a
reason (e.g. a partner/investor requirement) to do otherwise.

## Once decided

1. Drop the corresponding license text into `LICENSE` at the repo root
   (standard MIT/Apache text, with your name/org and the current year).
2. If not MIT, update `pyproject.toml`'s `license` field to match.
3. Cross out this blocker in `README.md`'s release checklist.
