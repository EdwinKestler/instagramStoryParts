# Vercel deployment and budget runbook

The web application is static. A user's source video and generated parts stay
inside that user's browser; there are no upload, storage, database, or server
processing endpoints in this deployment.

## Deploy

1. Push the repository to GitHub, GitLab, or Bitbucket.
2. In Vercel, select **Add New > Project** and import the repository.
3. Leave the project root at the repository root. `vercel.json` supplies the
   install command, build command, output directory, and response headers.
4. Deploy and verify the checks below.

For a CLI deployment, authenticate once and run from the repository root:

```powershell
npx vercel@latest login
npx vercel@latest
npx vercel@latest --prod
```

No secrets or environment variables are required.

The current test deployment is on Vercel Hobby, which costs $0 and is paused by
Vercel if it exceeds the included limits. Hobby is intended for personal,
non-commercial use. Upgrade to Pro only when the application is ready for a
commercial/public launch, then apply the spend controls below before sharing it.

If automatic Git deployments are wanted, first add GitHub as a Login Connection
in the Vercel account and then run `npx vercel@latest git connect`. CLI
deployments work without that repository connection.

## Required spend controls

Use a Vercel Pro team so spend management can pause production at the chosen
threshold. Configure these controls before sharing the URL:

- Monthly operational target: **$80 USD before tax**.
- Base Pro subscription allowance: **$20 USD/month**.
- Set the Spend Management amount to **$60** and explicitly enable **Pause
  production deployment**. With the $20 base, that targets an $80 total and
  leaves $20 headroom below the hard $100 requirement. Vercel automatically
  sends notifications at 50%, 75%, and 100% of that amount ($30, $45, and $60).
- Do not enable paid add-ons, Observability Plus, image optimization, managed
  storage, or server-side functions for this project.
- Review Spend Management after every release and once per week during public
  testing. Taxes are account-specific, so the reserve must also cover tax.

Spend Management applies at the team level. If the team hosts other projects,
their usage consumes the same limit; use a dedicated team or reduce this
project's thresholds accordingly.

## Traffic guardrails

The first processing run downloads and caches approximately 31 MB of
FFmpeg-WASM. A conservative public-beta limit is **1,000 uncached FFmpeg loads
per day** (30,000/month), approximately 930 GB of monthly transfer. A returning
browser normally uses the service-worker cache and does not fetch that engine
again.

The `estimateVercelProCost` function and its tests document this model. The UI
is otherwise a small static site and has no compute or storage charge path.
Vercel's dashboard is authoritative because bot traffic, cache misses, plan
changes, and traffic from other team projects can alter actual usage.

The estimator uses the high end of Vercel's published regional overage ranges:
$0.35/GB for Fast Data Transfer and $3.20/million Edge Requests. Current Pro
inclusions are 1 TB of transfer and 10 million requests per billing cycle.
Review the official [pricing page](https://vercel.com/pricing), [regional
pricing](https://vercel.com/docs/pricing/regional-pricing), and [Spend
Management documentation](https://vercel.com/docs/spend-management) before
launch because platform prices and controls can change.

If the 1,000/day cold-load guardrail is approached, keep the spend pause active
and introduce a CDN/WAF traffic rule before raising it. A client-only rate
limit is not a billing control because users can bypass it.

## Production verification

1. Open the deployment in a private browser window.
2. Select a short MP4 and create two parts.
3. Confirm DevTools **Network** contains no request carrying the source or an
   output media payload. Requests should only fetch application assets and the
   versioned FFmpeg engine.
4. Confirm generated parts download locally or are written through the browser
   directory picker. No cloud output directory exists.
5. Reload once and confirm the FFmpeg engine is served from cache.
6. Check response headers for CSP, COOP, COEP, `nosniff`, and the restrictive
   permissions policy.
7. Test the production URL on desktop Chromium and a real phone. Mobile browser
   memory limits vary, so start with short videos.

## Rollback

Use the Vercel deployment list to promote the last verified deployment. The
application has no server data migration or stored user media to roll back.
